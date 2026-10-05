#!/usr/bin/env python3
"""Bounded candidate check using the pinned Runner package; no registration.

Reuses the existing digest-checked package acquisition, environment filtering
and extraction helpers. Reports only aggregate outcomes, never failing inputs.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package", ROOT / "scripts/test-runner-package.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)
CANDIDATE = ROOT / "tests/unicode-policy-probe/start-candidate.json"
CANDIDATE_SHA = "14c8cfe5230d780ad64ec43f5c29c89863d1462ee47c90da390b1f9300273c93"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    evidence = args.output.resolve()
    evidence.mkdir(parents=True, exist_ok=False)
    pins = json.loads(package.PINS.read_text())
    rid = {("Linux", "x86_64"): "linux-x64", ("Darwin", "arm64"): "osx-arm64",
           ("Windows", "AMD64"): "win-x64"}.get((platform.system(), platform.machine()))
    report = {"status": "failed", "scope": "candidate parser integration; not production acceptance or Worker effects",
              "rid": rid, "runnerVersion": pins["runnerVersion"],
              "imageOS": os.environ.get("ImageOS"), "imageVersion": os.environ.get("ImageVersion"),
              "githubSha": os.environ.get("GITHUB_SHA"), "githubRunId": os.environ.get("GITHUB_RUN_ID")}
    try:
        report["phase"] = "candidate-identity"
        package.verify(CANDIDATE, CANDIDATE_SHA)
        if rid not in pins["packages"]:
            raise ValueError("unsupported platform")
        with tempfile.TemporaryDirectory(prefix="shoutx-unicode-policy-") as temporary:
            report["phase"] = "sdk-selection"
            work = Path(temporary).resolve()
            (work / "global.json").write_text(json.dumps({"sdk": {"version": pins["sdkVersion"], "rollForward": "disable"}}))
            sdk = subprocess.check_output(["dotnet", "--version"], cwd=work, text=True).strip()
            if sdk != pins["sdkVersion"]:
                raise ValueError("unexpected SDK")
            report["sdkVersion"] = sdk
            report["phase"] = "package-acquisition"
            pin = pins["packages"][rid]
            name = f'actions-runner-{rid}-{pins["runnerVersion"]}.{pin["extension"]}'
            archive = work / name
            if args.archive:
                shutil.copyfile(args.archive.resolve(), archive)
            else:
                package.download(f'https://github.com/actions/runner/releases/download/v{pins["runnerVersion"]}/{name}', archive, pin["size"])
            package.verify(archive, pin["sha256"], pin["size"])
            report["packageSha256"] = pin["sha256"]
            report["phase"] = "package-extraction"
            binary = work / "bin"
            package.extract_bin(archive, binary)
            config = json.loads((binary / "Runner.Worker.runtimeconfig.json").read_text())
            if config["runtimeOptions"].get("includedFrameworks") != [{"name": "Microsoft.NETCore.App", "version": pins["runtimeVersion"]}]:
                raise ValueError("unexpected package runtime")
            report["phase"] = "build"
            package.run(["dotnet", "build", str(ROOT / "tests/unicode-policy-probe/Probe.csproj"),
                         "-c", "Release", "-nodeReuse:false", "-p:UseSharedCompilation=false",
                         f"-p:RunnerBin={binary}", f"-p:BaseIntermediateOutputPath={work / 'obj'}/",
                         "-o", str(work / "probe")], evidence, "build", cwd=work)
            shutil.copyfile(work / "probe/Probe.dll", binary / "Probe.dll")
            env, removed = package.probe_environment(os.environ)
            report["removedEnvironmentNames"] = removed
            report["phase"] = "execute"
            exit_code = package.run(["dotnet", "exec", "--runtimeconfig", str(binary / "Runner.Worker.runtimeconfig.json"),
                                    "--depsfile", str(binary / "Runner.Worker.deps.json"), str(binary / "Probe.dll"),
                                    str(CANDIDATE), str(evidence / "probe.json")],
                                   evidence, "execute", env, cwd=work, check=False, timeout=900)
            observation = json.loads((evidence / "probe.json").read_text())
            report["phase"] = "verify-result"
            if (observation["candidateSha256"] != CANDIDATE_SHA
                    or observation["runtime"] != pins["runtimeVersion"]
                    or observation["runnerCommonSha256"] != package.digest(binary / "Runner.Common.dll")
                    or observation["coreLibrarySha256"] != package.digest(binary / "System.Private.CoreLib.dll")):
                raise ValueError("loaded identity mismatch")
            cultures = observation["results"]
            if ([c["culture"] for c in cultures] != ["", "en-US"]
                    or any(c["cases"] != 72 or c["startCases"] != 4422088
                           or c["headerCases"] != 3336189 for c in cultures)):
                raise ValueError("incomplete coverage")
            report["probe"] = observation
            report["exitCode"] = exit_code
            passed = all(not c["failures"] and c["startFailures"] == 0 and c["headerFailures"] == 0 for c in cultures)
            if (exit_code == 0) != passed:
                raise ValueError("inconsistent probe exit")
            report["status"] = "passed" if passed else "candidate-mismatch"
    except Exception as error:
        report["errorType"] = type(error).__name__
    (evidence / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "rid": rid}))
    return 0 if report["status"] == "passed" else 1

if __name__ == "__main__":
    raise SystemExit(main())
