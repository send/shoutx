"""Ancestor Worker module metadata; never retain memory dumps or environments.

Mapped names and on-disk hashes are not active-backend or loaded-byte attestation.
Only fixed runtime/ICU module classes are projected; raw maps/paths are discarded.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import platform
import re
import stat
import subprocess
import sys

from hosted_worker import Unavailable, at_stage, identity, require, worker_ancestor

MAP_CAP = 4 * 1024 * 1024
FILE_CAP = 128 * 1024 * 1024
LINUX_NAMES = {
    "coreclr": r"libcoreclr\.so",
    "globalizationShim": r"libSystem\.Globalization\.Native\.so",
    "icuCommon": r"libicuuc\.so\.[0-9.]+",
    "icuInternational": r"libicui18n\.so\.[0-9.]+",
    "icuData": r"libicudata\.so\.[0-9.]+",
}
WINDOWS_NAMES = {"coreclr.dll", "icu.dll", "icuuc.dll", "icuin.dll", "icudt.dll",
                 "system.globalization.native.dll"}


def linux_paths(raw, identities=None):
    require(len(raw) <= MAP_CAP, "module-metadata-size-limit")
    found = set()
    for line in raw.decode("utf-8", errors="strict").splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6:
            continue
        path = fields[5]
        deleted = path.endswith(" (deleted)")
        if deleted:
            path = path[:-10]
        if any(re.fullmatch(pattern, Path(path).name) for pattern in LINUX_NAMES.values()):
            require(re.fullmatch(r"[0-9a-f]+-[0-9a-f]+", fields[0]) and
                    re.fullmatch(r"[r-][w-][x-][ps]", fields[1]) and
                    re.fullmatch(r"[0-9a-f]+", fields[2]) and
                    re.fullmatch(r"[0-9a-f]+:[0-9a-f]+", fields[3]) and
                    re.fullmatch(r"[0-9]+", fields[4]), "unsupported-module-map-record")
            require(path.startswith("/") and "\\" not in path, "unsupported-module-path")
            if identities is not None:
                device = tuple(int(part, 16) for part in fields[3].split(":"))
                file_id = (*device, int(fields[4]))
                require(path not in identities or identities[path] == file_id,
                        "ambiguous-mapped-file-identity")
                identities[path] = file_id
            found.add((path, deleted))
    return found


def mac_paths(raw, binary_dir, pid):
    require(len(raw) <= MAP_CAP, "module-metadata-size-limit")
    lines = raw.decode("utf-8", errors="strict").splitlines()
    require([line for line in lines if line.startswith("p")] == [f"p{pid}"],
            "unexpected-module-process")
    # lsof text-file metadata may omit shared-cache images. Omission is unknown.
    paths = (str(binary_dir / "libcoreclr.dylib"),
             str(binary_dir / "libSystem.Globalization.Native.dylib"),
             "/usr/lib/libicucore.A.dylib")
    return {(path, False) for path in paths if "n" + path in lines}


def module_paths(pid, binary_dir, system, identities=None):
    if system == "Linux":
        with Path(f"/proc/{pid}/maps").open("rb") as stream:
            return linux_paths(stream.read(MAP_CAP + 1), identities)
    if system == "Darwin":
        result = subprocess.run(["/usr/sbin/lsof", "-nP", "-a", "-p", str(pid), "-d", "txt", "-Fn"],
                                capture_output=True, timeout=30)
        require(result.returncode == 0, "module-metadata-unavailable")
        return mac_paths(result.stdout, binary_dir, pid)
    require(system == "Windows", "unsupported-module-platform")
    script = r'''
$ErrorActionPreference = 'Stop'
$targetProcess = Get-Process -Id ([int]$env:SHOUTX_MODULE_PID)
$paths = @($targetProcess.Modules | ForEach-Object {
    if ($_.ModuleName -and $_.ModuleName.ToLowerInvariant() -in @(__MODULE_NAMES__)) {
        $_.FileName
    }
})
ConvertTo-Json -InputObject $paths -Compress
'''
    script = script.replace("__MODULE_NAMES__", ",".join("'" + name + "'" for name in sorted(WINDOWS_NAMES)))
    result = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
                            env=dict(os.environ, SHOUTX_MODULE_PID=str(pid)),
                            capture_output=True, timeout=30)
    require(result.returncode == 0, "module-metadata-unavailable")
    require(len(result.stdout) <= MAP_CAP, "module-metadata-size-limit")
    paths = json.loads(result.stdout)
    require(isinstance(paths, list) and len(paths) <= 64 and
            all(isinstance(path, str) and PureWindowsPath(path).is_absolute() and
                re.fullmatch(r"[A-Za-z]:", PureWindowsPath(path).drive) and
                PureWindowsPath(path).name.lower() in WINDOWS_NAMES for path in paths),
            "unsupported-module-result")
    return {(path, False) for path in paths}


def disk_hash(path, deleted, expected_identity=None):
    if deleted:
        return {"onDiskStatus": "mapped-path-deleted", "onDiskSha256": None}
    try:
        digest, count = hashlib.sha256(), 0
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
        try:
            stream = os.fdopen(fd, "rb")
        except Exception:
            os.close(fd)
            raise
        with stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_size <= FILE_CAP,
                    "unsupported-module-file")
            if expected_identity is not None:
                require(expected_identity[2] > 0 and
                        (os.major(before.st_dev), os.minor(before.st_dev), before.st_ino) == expected_identity,
                        "module-file-identity-mismatch")
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                count += len(block)
                require(count <= FILE_CAP, "module-file-size-limit")
                digest.update(block)
            after = os.fstat(stream.fileno())
            require(count == before.st_size == after.st_size and
                    before.st_mtime_ns == after.st_mtime_ns,
                    "module-file-changed-during-read")
        return {"onDiskStatus": "observed", "onDiskSha256": digest.hexdigest(),
                "mappedFileIdentityStatus": "matched" if expected_identity is not None else "not-observed"}
    except OSError:
        # Shared-cache-only macOS images may have no separately readable file.
        return {"onDiskStatus": "unavailable", "onDiskSha256": None}
    except Unavailable as error:
        return {"onDiskStatus": "unavailable", "onDiskSha256": None, "reason": str(error)}


def observe():
    pid, executable = at_stage("ancestry", worker_ancestor)
    require(executable.is_absolute() and executable.name in ("Runner.Worker", "Runner.Worker.exe"),
            "worker-path-unavailable")
    system = platform.system()
    identities = {}
    paths = at_stage("module-metadata", module_paths, pid, executable.parent, system, identities)
    require(0 < len(paths) <= 16, "missing-or-ambiguous-module-metadata")
    path_type = PureWindowsPath if system == "Windows" else Path
    names = [path_type(path).name.lower() for path, _ in paths]
    require(len(set(names)) == len(names), "ambiguous-module-metadata")
    modules = sorted([{"name": path_type(path).name, "mappedPathDeleted": deleted,
                       **disk_hash(path, deleted, identities.get(path))} for path, deleted in paths],
                     key=lambda module: module["name"].lower())
    patterns = (LINUX_NAMES if system == "Linux" else
                {"coreclr": r"libcoreclr\.dylib", "globalizationShim": r"libSystem\.Globalization\.Native\.dylib",
                 "icuSystem": r"libicucore\.A\.dylib"} if system == "Darwin" else
                {name: re.escape(name) for name in sorted(WINDOWS_NAMES)})
    classes = {name: ("observed" if any(re.fullmatch(pattern, module["name"], re.I)
                                      for module in modules) else "not-observed")
               for name, pattern in patterns.items()}
    require(at_stage("ancestry-recheck", worker_ancestor) == (pid, executable),
            "worker-ancestry-changed")
    return {"status": "observed-module-metadata", "ancestorWorkerPid": pid,
            "method": {"Linux": "proc-maps", "Darwin": "lsof-text-files",
                       "Windows": "process-modules"}[system],
            "modules": modules, "selectedClasses": classes,
            "activeBackend": None, "effectiveData": None,
            "loadedBytesAttested": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"schemaVersion": 1, "status": "unavailable",
              "scope": "selected ancestor Worker module metadata and on-disk identities only"}
    try:
        report["identity"] = identity(os.environ)
        report.update(observe())
    except Unavailable as error:
        report["reason"] = str(error)
    except Exception:
        report["reason"] = "module-observation-unavailable"
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
            output.write("\n")
    except OSError:
        print("Could not write hosted module observation.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
