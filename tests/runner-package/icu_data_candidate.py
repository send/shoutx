"""Research draft: hash one candidate data file, never publish its contents.

The caller must select the fixed native Windows-directory-relative path.
An observation identifies a candidate file; it does not identify effective ICU
data, establish a reference match, or load any vendor code.
"""
import hashlib
import ctypes
from pathlib import Path, PureWindowsPath
import sys

from icu_package_inventory import inventory

DATA_CAP = 64 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
# Pinned gate from docs/compatibility/unicode-reference-inputs.md,
# "Data candidate observation and bounded package inspection" (run 37225475724).
# This identifies the inspected candidate, not its effective consumer binding.
PACKAGE_SIZE = 31158064
PACKAGE_SHA256 = "8b1eb674fd6493f2009a8305b0ab0ed083754e9d0590d12d1cae4cf95f6268e9"


def native_data_path():
    if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise ValueError("requires-64-bit-windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    get_directory = kernel.GetSystemWindowsDirectoryW
    get_directory.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
    get_directory.restype = ctypes.c_uint
    buffer = ctypes.create_unicode_buffer(32768)
    size = get_directory(buffer, len(buffer))
    if not 0 < size < len(buffer) or not PureWindowsPath(buffer.value).is_absolute():
        raise ValueError("windows-directory")
    return Path(buffer.value) / "globalization" / "icu" / "icudtl.dat"


def collect_data_candidate():
    try:
        path = native_data_path()
    except ctypes.ArgumentError:
        return {"status": "unavailable", "reason": "system-api-binding-error"}
    except (OSError, AttributeError):
        return {"status": "unavailable", "reason": "system-api-unavailable"}
    except ValueError:
        return {"status": "unavailable", "reason": "windows-directory-unavailable"}
    return inspect_data_candidate(path)


def inspect_data_candidate(path):
    digest = hashlib.sha256()
    size = 0
    data = bytearray()
    try:
        with path.open("rb") as stream:
            while True:
                block = stream.read(min(CHUNK_SIZE, DATA_CAP + 1 - size))
                if not block:
                    break
                size += len(block)
                if size > DATA_CAP:
                    return {"status": "unavailable", "reason": "file-size-limit"}
                digest.update(block)
                data.extend(block)
    except FileNotFoundError:
        return {"status": "unavailable", "reason": "file-not-found"}
    except PermissionError:
        return {"status": "unavailable", "reason": "access-denied"}
    except OSError:
        return {"status": "unavailable", "reason": "file-read-error"}
    sha256 = digest.hexdigest()
    result = {"status": "observed-candidate", "size": size, "sha256": sha256}
    if size != PACKAGE_SIZE or sha256 != PACKAGE_SHA256:
        result["inventory"] = {"status": "unavailable", "reason": "candidate-hash-mismatch"}
    else:
        try:
            result["inventory"] = {"status": "observed-structure",
                                   **inventory(data, "icudt72l")}
        except ValueError as error:
            reason = "prefix-mismatch" if str(error) == "prefix-mismatch" else "unsupported-package-layout"
            result["inventory"] = {"status": "unavailable", "reason": reason}
    return result
