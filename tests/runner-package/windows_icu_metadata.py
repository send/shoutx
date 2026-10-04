"""Acquisition locator only: never load or publish the inspected vendor DLL."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/compatibility/evidence/hosted-worker-modules-37184265280.json"
FILE_CAP = 8 * 1024 * 1024
REASONS = frozenset({"dos-header", "pe-header", "pe-layout", "pe-bounds", "pe32plus",
                     "image-size", "requires-64-bit-windows", "system-directory"})


def fixed_reason(error):
    token = str(error)
    return token if token in REASONS else "inspection-error"


def reference_digest(raw):
    evidence = json.loads(raw)
    rows = [row for row in evidence["rows"] if row["rid"] == "win-x64"]
    if len(rows) != 1:
        raise ValueError("reference-row")
    modules = [item for item in rows[0]["moduleObservation"]["modules"]
               if item["name"] == "icu.dll" and item["onDiskStatus"] == "observed"]
    if len(modules) != 1:
        raise ValueError("reference-module")
    digest = modules[0]["onDiskSha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("reference-hash")
    return digest


def pe_key(data):
    """Read the x64 PE fields used by Microsoft's binary symbol-store key."""
    if len(data) < 64 or data[:2] != b"MZ":
        raise ValueError("dos-header")
    offset = struct.unpack_from("<I", data, 60)[0]
    if offset < 64 or offset > len(data) - 24 or data[offset:offset + 4] != b"PE\0\0":
        raise ValueError("pe-header")
    machine, sections, timestamp = struct.unpack_from("<HHI", data, offset + 4)
    optional_size = struct.unpack_from("<H", data, offset + 20)[0]
    optional = offset + 24
    if machine != 0x8664 or not 1 <= sections <= 96 or optional_size < 112:
        raise ValueError("pe-layout")
    if optional + optional_size + sections * 40 > len(data):
        raise ValueError("pe-bounds")
    if struct.unpack_from("<H", data, optional)[0] != 0x20B:
        raise ValueError("pe32plus")
    image_size = struct.unpack_from("<I", data, optional + 56)[0]
    if not 0 < image_size <= 64 * 1024 * 1024:
        raise ValueError("image-size")
    return {"machine": machine, "timeDateStamp": timestamp,
            "sizeOfImage": image_size, "symbolKey": f"{timestamp:08x}{image_size:x}"}


def inspect_file(path, expected):
    try:
        with path.open("rb") as stream:
            data = stream.read(FILE_CAP + 1)
    except FileNotFoundError:
        return {"status": "unavailable", "reason": "file-not-found"}
    except PermissionError:
        return {"status": "unavailable", "reason": "access-denied"}
    except OSError:
        return {"status": "unavailable", "reason": "file-read-error"}
    if len(data) > FILE_CAP:
        return {"status": "unavailable", "reason": "file-size-limit"}
    digest = hashlib.sha256(data).hexdigest()
    result = {"size": len(data), "sha256": digest, "status": "candidate-mismatch"}
    # Do not promote a different same-version DLL's fields into target metadata.
    if digest == expected:
        try:
            result.update(pe_key(data))
            result["status"] = "reference-hash-match"
        except ValueError as error:
            result["status"] = "reference-hash-match-pe-unavailable"
            result["reason"] = fixed_reason(error)
    return result


def system_icu_path():
    if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise ValueError("requires-64-bit-windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    get_directory = kernel.GetSystemDirectoryW
    get_directory.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
    get_directory.restype = ctypes.c_uint
    buffer = ctypes.create_unicode_buffer(32768)
    size = get_directory(buffer, len(buffer))
    if not 0 < size < len(buffer):
        raise ValueError("system-directory")
    return Path(buffer.value) / "icu.dll"


def identity():
    patterns = {"GITHUB_RUN_ID": r"[0-9]{1,20}", "GITHUB_RUN_ATTEMPT": r"[0-9]{1,8}",
                "GITHUB_SHA": r"[0-9a-f]{40}", "ImageOS": r"[A-Za-z0-9-]{1,64}",
                "ImageVersion": r"[0-9.]{1,64}", "SHOUTX_SOURCE_HEAD": r"[0-9a-f]{40}",
                "GITHUB_EVENT_NAME": r"pull_request|workflow_dispatch",
                "GITHUB_JOB": r"[A-Za-z0-9_-]{1,100}",
                "GITHUB_REPOSITORY": r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}"}
    return {key: value if re.fullmatch(pattern, value) else None
            for key, pattern in patterns.items() if (value := os.environ.get(key)) is not None}


def collect():
    raw = EVIDENCE.read_bytes()
    expected = reference_digest(raw)
    report = {"schemaVersion": 1, "kind": "windows-icu-acquisition-locator",
              "referenceEvidenceSha256": hashlib.sha256(raw).hexdigest(),
              "expectedSha256": expected, "identity": identity(), "name": "icu.dll",
              "loadedBytesAttested": False, "effectiveDataEstablished": False}
    try:
        path = system_icu_path()
    except ctypes.ArgumentError:
        report["candidate"] = {"status": "unavailable", "reason": "system-api-binding-error"}
    except OSError:
        # No exception text, paths, environment values or vendor bytes escape.
        report["candidate"] = {"status": "unavailable", "reason": "system-api-unavailable"}
    except ValueError as error:
        report["candidate"] = {"status": "unavailable", "reason": fixed_reason(error)}
    else:
        report["candidate"] = inspect_file(path, expected)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = collect()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2) + "\n")
    except (OSError, ValueError, KeyError, TypeError):
        print("ICU acquisition metadata could not be recorded", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
