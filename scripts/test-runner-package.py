#!/usr/bin/env python3
"""Package-backed parser evidence; Python 3.10+, .NET SDK, and Cargo required.

No runner registration. Downloads are anonymous and digest-checked before use.
Only root bin/ regular files are extracted into a fresh private staging tree.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PINS = ROOT / "tests/runner-package/pins.json"


def digest(path):
    with path.open("rb") as stream:
        value = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def verify(path, expected, size=None):
    if (size is not None and path.stat().st_size != size) or digest(path) != expected:
        raise ValueError("pinned download identity mismatch")


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise ValueError("non-HTTPS redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, destination, limit):
    if not url.startswith("https://"):
        raise ValueError("non-HTTPS URL")
    opener = urllib.request.build_opener(HTTPSRedirect())
    with opener.open(url, timeout=60) as response, destination.open("xb") as output:
        total = 0
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > limit:
                raise ValueError("download exceeds limit")
            output.write(chunk)


def bin_name(name):
    # Ignore everything except immediate bin children; never interpret archive paths.
    parts = PurePosixPath(name).parts
    if len(parts) != 2 or parts[0] != "bin":
        return None
    leaf = parts[1]
    if leaf in (".", "..") or any(c in leaf for c in "\\:\x00"):
        raise ValueError("invalid bin member")
    return leaf


def extract_bin(archive, destination):
    destination.mkdir()
    seen = set()
    total = 0

    def save(name, size, mode, stream):
        nonlocal total
        key = name.casefold()
        if key in seen or size < 0 or size > 128 * 1024 * 1024:
            raise ValueError("invalid or duplicate package member")
        seen.add(key)
        total += size
        if total > 1024 * 1024 * 1024:
            raise ValueError("package bin exceeds limit")
        path = destination / name
        with path.open("xb") as output:
            shutil.copyfileobj(stream, output)
        if path.stat().st_size != size:
            raise ValueError("member size mismatch")
        path.chmod(mode & 0o777)

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                name = bin_name(member.filename)
                if name is None or member.is_dir():
                    continue
                mode = member.external_attr >> 16
                if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                    raise ValueError("non-regular bin member")
                with package.open(member) as stream:
                    save(name, member.file_size, mode or 0o644, stream)
    else:
        with tarfile.open(archive, "r:gz") as package:
            for member in package:
                name = bin_name(member.name)
                if name is None or member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError("non-regular bin member")
                with package.extractfile(member) as stream:
                    save(name, member.size, member.mode, stream)


def run(command, evidence, label, env=None, cwd=ROOT):
    with (evidence / (label + ".log")).open("wb") as log:
        subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=600)


def verify_coreclr(trace, binary, rid):
    matches = re.findall(r"^CoreCLR path = '(.*)', CoreCLR dir = ", trace, re.MULTILINE)
    name = {"linux-x64": "libcoreclr.so", "osx-arm64": "libcoreclr.dylib", "win-x64": "coreclr.dll"}[rid]
    if len(matches) != 1 or Path(matches[0]).resolve() != (binary / name).resolve():
        raise ValueError("host did not select package CoreCLR")
    return name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new evidence directory")
    parser.add_argument("--archive", type=Path, help="optional cached archive (still verified)")
    args = parser.parse_args()
    evidence = args.output.resolve()
    evidence.mkdir(parents=True, exist_ok=False)  # Never mix runs or reuse stale results.
    pins = json.loads(PINS.read_text())
    rid = {("Linux", "x86_64"): "linux-x64", ("Darwin", "arm64"): "osx-arm64",
           ("Windows", "AMD64"): "win-x64"}.get((platform.system(), platform.machine()))
    record = {"schemaVersion": 1, "status": "failed", "rid": rid, "pins": pins,
              "scope": "published-package parser probe; not a live Worker process",
              "githubRunId": os.environ.get("GITHUB_RUN_ID"),
              "githubSha": os.environ.get("GITHUB_SHA"),
              "imageOS": os.environ.get("ImageOS"), "imageVersion": os.environ.get("ImageVersion")}
    try:
        if rid not in pins["packages"]:
            raise ValueError("unsupported package probe platform")
        with tempfile.TemporaryDirectory(prefix="shoutx-runner-package-") as temporary:
            work = Path(temporary).resolve()
            record["phase"] = "select-sdk"
            # Hosted images contain newer SDKs too; setup-dotnet does not select
            # a default. Keep the selection local, with no repository-wide change.
            (work / "global.json").write_text(json.dumps({"sdk": {
                "version": pins["sdkVersion"], "rollForward": "disable"}}))
            sdk = subprocess.check_output(["dotnet", "--version"], cwd=work, text=True).strip()
            record["buildSdk"] = sdk
            if sdk != pins["sdkVersion"]:
                raise ValueError("unexpected build SDK")
            record["phase"] = "verify-package"
            pin = pins["packages"][rid]
            name = f'actions-runner-{rid}-{pins["runnerVersion"]}.{pin["extension"]}'
            url = f'https://github.com/actions/runner/releases/download/v{pins["runnerVersion"]}/{name}'
            archive = args.archive.resolve() if args.archive else work / name
            if not args.archive:
                download(url, archive, pin["size"])
            verify(archive, pin["sha256"], pin["size"])
            record["package"] = {"url": url, "sha256": digest(archive), "size": archive.stat().st_size}
            binary = work / "bin"
            extract_bin(archive, binary)
            files = {p.name: digest(p) for p in sorted(binary.iterdir())}
            (evidence / "package-bin-sha256.json").write_text(json.dumps(files, indent=2) + "\n")
            config = json.loads((binary / "Runner.Worker.runtimeconfig.json").read_text())
            record["workerRuntimeConfig"] = config
            expected = [{"name": "Microsoft.NETCore.App", "version": pins["runtimeVersion"]}]
            if config["runtimeOptions"].get("includedFrameworks") != expected or "framework" in config["runtimeOptions"]:
                raise ValueError("unexpected worker runtime config")
            for source in pins["sources"]:
                path = evidence / source["name"]
                download(source["url"], path, 1024 * 1024)
                verify(path, source["sha256"])
            record["phase"] = "build-probe-and-corpora"
            for kind in ("mask", "annotation"):
                env = os.environ.copy()
                env["CARGO_TARGET_DIR"] = str(work / "cargo")
                env[f"SHOUTX_{kind.upper()}_CORPUS_PATH"] = str(evidence / f"{kind}-corpus.json")
                run(["cargo", "test", "--locked", "--features", "unstable-github-actions-stdout",
                     "--test", f"{kind}_runner_fixture", f"export_{kind}_corpus", "--", "--ignored"],
                    evidence, f"generate-{kind}", env)
            run(["dotnet", "build", str(ROOT / "tests/runner-package/Probe.csproj"), "-c", "Release",
                 f"-p:RunnerBin={binary}", f"-p:BaseIntermediateOutputPath={work / 'obj'}/",
                 "-o", str(work / "probe")], evidence, "build-probe", cwd=work)
            shutil.copyfile(work / "probe/Probe.dll", binary / "Probe.dll")
            # Self-contained worker config selects local hostpolicy/coreclr, not SDK runtime.
            probe_env = os.environ.copy()
            probe_env["COREHOST_TRACE"] = "1"
            probe_env["COREHOST_TRACEFILE"] = str(evidence / "corehost.log")
            record["phase"] = "execute-probe"
            run(["dotnet", "exec", "--runtimeconfig", str(binary / "Runner.Worker.runtimeconfig.json"),
                 "--depsfile", str(binary / "Runner.Worker.deps.json"), str(binary / "Probe.dll"),
                 str(evidence / "probe.json"), str(evidence / "mask-corpus.json"),
                 str(evidence / "annotation-corpus.json")], evidence, "execute-probe", probe_env, cwd=work)
            record["phase"] = "verify-loaded-identities"
            coreclr = verify_coreclr((evidence / "corehost.log").read_text(encoding="utf-8"), binary, rid)
            record["selectedCoreClr"] = {"file": coreclr, "sha256": files[coreclr]}
            record["corehostTraceSha256"] = digest(evidence / "corehost.log")
            probe = json.loads((evidence / "probe.json").read_text())
            if probe["status"] != "passed":
                raise ValueError("probe did not pass")
            for key in ("coreLibrary", "parserAssembly"):
                identity = probe[key]
                if files.get(identity["file"]) != identity["sha256"]:
                    raise ValueError("loaded assembly differs from package")
            build = f'{pins["runtimeVersion"]}+{pins["runtimeCommit"]}'
            if probe["coreLibrary"]["informationalVersion"] != build:
                raise ValueError("runtime build differs from inspected source")
            runner_build = f'{pins["runnerVersion"]}+{pins["runnerCommit"]}'
            if probe["parserAssembly"]["informationalVersion"] != runner_build:
                raise ValueError("parser build differs from pinned Runner source")
            for culture in probe["cultures"]:
                icu = culture["icu"]
                if icu is not None and files.get(icu["file"]) != icu["sha256"]:
                    raise ValueError("ICU bridge differs from package")
            for name, sha in files.items():
                if digest(binary / name) != sha:
                    raise ValueError("package binary changed during probe")
            record["status"] = "passed"
            record["phase"] = "complete"
    except Exception as error:
        record["errorType"] = type(error).__name__
        if isinstance(error, ValueError):
            record["errorRule"] = str(error)
        print("Runner package evidence failed; inspect the evidence directory.")
        return 1
    finally:
        (evidence / "evidence.json").write_text(json.dumps(record, indent=2) + "\n")
    print("Runner package evidence passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
