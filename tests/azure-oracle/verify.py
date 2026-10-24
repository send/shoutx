#!/usr/bin/env python3
"""Bounded, actual-upstream parser test; never emit captured command data."""
import base64
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
COMMIT = "efa064fee06c75b31cabc0451857ad1e294649c7"
SOURCES = {
    "src/Microsoft.VisualStudio.Services.Agent/Command.cs":
        "905a8f58e4235e4b28fd18bacd2bed5ceb4390cff4516ffd786363441b8a91c6",
    "src/Agent.Sdk/CommandStringConvertor.cs":
        "9f962d3fc218e395b3c90770b5c7c73c809e813b86f2f50fad95c24ee167418b",
}


def run(args, **kwargs):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=180, **kwargs)
    if result.returncode:
        raise RuntimeError("subprocess failed; captured output withheld")
    return result


def corpus(binary):
    cases = []

    def add(args, data, event, properties):
        result = run([str(binary), *args], input=data.encode("utf-8"))
        if result.stderr:
            raise RuntimeError("producer wrote diagnostics")
        row = {"record": base64.b64encode(result.stdout).decode("ascii"),
               "decode": True, "event": event, "properties": properties,
               "data": data, "match": True}
        cases.append(row)

    samples = ["", " ", "\r", "\n", "\r\n", "a\r\nb\rc\n\n",
               "%0A%0D%3B%5D%AZP25%25%0a", "];variable=OTHER;",
               "\n##vso[task.setvariable variable=SHOUTX_INJECTED;]yes",
               "\u0301\u200b\ufeffไทย日本語😀", "\u0085\u2028\u2029",
               "##[error]x", "::error::x"]
    rng = random.Random(20261020)
    for _ in range(320):
        chars = []
        for _ in range(rng.randrange(1, 80)):
            n = rng.randrange(1, 0x110000)
            if 0xD800 <= n <= 0xDFFF:
                n = 0x0301
            chars.append(chr(n))
        samples.append("%0A;]\r\n".join(["".join(chars), "\u200b"]))
    for index, data in enumerate(samples):
        flags = ["--output", "--read-only"] if index % 2 else []
        add(["azure-pipelines:variable", *flags, "Result"], data, "setvariable",
            {"variable": "Result", "isOutput": "true" if flags else "false",
             "isReadOnly": "true" if flags else "false"})
        if data:
            severity = "warning" if index % 2 else "error"
            props = {"type": severity}
            args = [f"azure-pipelines:{severity}"]
            if index % 3:
                file = "\u0301src/a];type=error%0A\n.cs"
                code = "\u200bE;]%=0A"
                args += ["--file", file, "--line", "001", "--column", "02", "--code", code]
                props.update(sourcepath=file, linenumber="1", columnnumber="2", code=code)
            add(args, data, "logissue", props)

    root = "C:\\" if os.name == "nt" else "/"
    for sample in samples:
        # Native PATH policy, not the variable/issue newline policy.
        tail = sample.translate(str.maketrans("", "", '\r\n;"' if os.name == "nt" else "\r\n:"))
        add(["azure-pipelines:path"], root + tail, "prependpath", {})

    # Prove the matcher notices a configuration mismatch, wrong command,
    # property mismatch, payload mismatch, and an additional physical line.
    original = next(c for c in cases if "%0A" in c["data"])
    cases.append(dict(original, decode=False, match=False))
    cases.append(dict(original, event="logissue", match=False))
    cases.append(dict(original, properties={"variable": "OTHER"}, match=False))
    cases.append(dict(original, data="wrong value", match=False))
    cases.append(dict(original, match=False, record=base64.b64encode(
        base64.b64decode(original["record"]) + b"##vso[task.complete]x\n").decode("ascii")))

    for sample in samples:
        single = sample.replace("\r", "").replace("\n", "")
        if single:
            add(["azure-pipelines:mask"], single, "setsecret", {})

    batches = samples + ["\r\na\r\n\r\nb\rc\n \n\t\na\n",
                         "x\n" * 1024, "%" * 1_048_576,
                         "\n\r\n" + "\n".join(str(n) for n in range(1024))]
    batch_original = None
    for data in batches:
        # Independent contract selection, not the Rust splitting implementation.
        entries = [part for part in re.split(r"\r\n|\r|\n", data) if part != ""]
        if not entries:
            continue
        result = run([str(binary), "azure-pipelines:mask", "--each-line"],
                     input=data.encode("utf-8"))
        if result.stderr:
            raise RuntimeError("producer wrote diagnostics")
        row = {"record": base64.b64encode(result.stdout).decode("ascii"),
               "decode": True, "match": True,
               "records": [{"event": "setsecret", "properties": {}, "data": entry}
                           for entry in entries]}
        cases.append(row)
        if entries == ["a", "b", "c", " ", "\t", "a"]:
            batch_original = row
    if batch_original is None:
        raise RuntimeError("missing batch control source")
    lines = base64.b64decode(batch_original["record"]).splitlines(keepends=True)
    for altered in [lines[:-1], list(reversed(lines)), lines + lines[:1],
                    lines[:1] + lines[2:], lines + [b"##vso[task.complete]x\n"]]:
        cases.append(dict(batch_original, match=False,
                          record=base64.b64encode(b"".join(altered)).decode("ascii")))
    cases.append(dict(batch_original, match=False, records=[
        dict(entry, properties={"unexpected": "yes"})
        for entry in batch_original["records"]]))
    return cases


def main():
    if len(sys.argv) != 2:
        raise RuntimeError("provide the built shoutx executable")
    binary = Path(sys.argv[1]).resolve(strict=True)
    cases = corpus(binary)
    with tempfile.TemporaryDirectory(prefix="shoutx-azure-oracle-") as temp:
        work = Path(temp)
        for name in ["Oracle.csproj", "Program.cs"]:
            shutil.copyfile(ROOT / name, work / name)
        for source, digest in SOURCES.items():
            url = f"https://raw.githubusercontent.com/microsoft/azure-pipelines-agent/{COMMIT}/{source}"
            with urllib.request.urlopen(url, timeout=30) as response:
                content = response.read(128 * 1024 + 1)
            if len(content) > 128 * 1024 or hashlib.sha256(content).hexdigest() != digest:
                raise RuntimeError("upstream source hash mismatch")
            (work / Path(source).name).write_bytes(content)
        shutil.copyfile(ROOT / "UPSTREAM-LICENSE.txt", work / "UPSTREAM-LICENSE.txt")
        env = dict(os.environ, DOTNET_NOLOGO="1", DOTNET_CLI_TELEMETRY_OPTOUT="1")
        run(["dotnet", "build", str(work / "Oracle.csproj"), "--nologo", "-o", str(work / "out")],
            env=env)
        payload = "".join(json.dumps(c, ensure_ascii=True) + "\n" for c in cases).encode()
        result = run(["dotnet", str(work / "out/Oracle.dll")], input=payload, env=env)
        report = json.loads(result.stdout)
        if report != {"cases": len(cases), "negativeControls": 11} or result.stderr:
            raise RuntimeError("missing source-parser results")
        print(json.dumps({"agentCommit": COMMIT, "scope": "source-parser-only", **report}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit("Azure oracle failed; no input/captured output disclosed")
