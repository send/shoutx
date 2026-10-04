import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import icu_data_candidate as probe
from test_icu_package_inventory import fixture


class DataCandidateTests(unittest.TestCase):
    def test_native_path_and_return_bounds(self):
        class Function:
            def __init__(self, value, result):
                self.value, self.result = value, result
            def __call__(self, buffer, count):
                self.count = count
                buffer.value = self.value
                return self.result
        class Kernel:
            pass
        kernel = Kernel()
        for value, result, accepted in [(r"C:\Windows", 10, True),
                                         ("C:\\", 3, True), ("C:", 2, False),
                                         (r"C:\Windows", 0, False),
                                         (r"C:\Windows", 32767, True),
                                         (r"C:\Windows", 32768, False)]:
            kernel.GetSystemWindowsDirectoryW = Function(value, result)
            with patch.object(probe.sys, "platform", "win32"), \
                    patch.object(probe.ctypes, "sizeof", return_value=8), \
                    patch.object(probe.ctypes, "WinDLL", return_value=kernel, create=True):
                if accepted:
                    expected = Path(value) / "globalization" / "icu" / "icudtl.dat"
                    self.assertEqual(probe.native_data_path(), expected)
                else:
                    with self.assertRaises(ValueError):
                        probe.native_data_path()
                self.assertEqual(kernel.GetSystemWindowsDirectoryW.count, 32768)

    def test_api_failures_are_sanitized(self):
        for error, reason in [(probe.ctypes.ArgumentError("PRIVATE"), "system-api-binding-error"),
                              (OSError("PRIVATE"), "system-api-unavailable"),
                              (AttributeError("PRIVATE"), "system-api-unavailable"),
                              (ValueError("PRIVATE"), "windows-directory-unavailable")]:
            with patch.object(probe, "native_data_path", side_effect=error):
                self.assertEqual(probe.collect_data_candidate(),
                                 {"status": "unavailable", "reason": reason})
        with patch.object(probe.sys, "platform", "win32"), \
                patch.object(probe.ctypes, "sizeof", return_value=8), \
                patch.object(probe.ctypes, "WinDLL", return_value=object(), create=True):
            self.assertEqual(probe.collect_data_candidate(),
                             {"status": "unavailable", "reason": "system-api-unavailable"})

    def test_streamed_digest_and_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.dat"
            with patch.object(probe, "DATA_CAP", 16), patch.object(probe, "CHUNK_SIZE", 3):
                for data in (b"", b"abcdefg", b"0123456789abcdef"):
                    path.write_bytes(data)
                    self.assertEqual(probe.inspect_data_candidate(path),
                                     {"status": "observed-candidate", "size": len(data),
                                      "sha256": hashlib.sha256(data).hexdigest(),
                                      "inventory": {"status": "unavailable", "reason": "candidate-hash-mismatch"}})
                path.write_bytes(b"0123456789abcdefg")
                self.assertEqual(probe.inspect_data_candidate(path),
                                 {"status": "unavailable", "reason": "file-size-limit"})

    def test_inventory_requires_exact_size_and_hash(self):
        data = fixture()
        digest = hashlib.sha256(data).hexdigest()
        for size, sha in [(len(data) + 1, digest), (len(data), "0" * 64)]:
            with self.subTest(size=size, sha=sha), \
                    patch.object(Path, "open", return_value=io.BytesIO(data)), \
                    patch.object(probe, "PACKAGE_SIZE", size), \
                    patch.object(probe, "PACKAGE_SHA256", sha), \
                    patch.object(probe, "inventory", side_effect=AssertionError("unexpected parse")):
                result = probe.inspect_data_candidate(Path("fixture"))
                self.assertEqual(result, {"status": "observed-candidate", "size": len(data),
                                          "sha256": digest, "inventory": {
                                              "status": "unavailable", "reason": "candidate-hash-mismatch"}})

    def test_inventory_uses_same_single_read_and_sanitizes_layout_failure(self):
        for valid in (True, False):
            data = fixture()
            if not valid:
                data[2] = 0
            with patch.object(Path, "open", return_value=io.BytesIO(data)) as opened, \
                    patch.object(probe, "PACKAGE_SIZE", len(data)), \
                    patch.object(probe, "PACKAGE_SHA256", hashlib.sha256(data).hexdigest()), \
                    patch.object(probe, "inventory", wraps=probe.inventory) as inspected:
                result = probe.inspect_data_candidate(Path("fixture"))
                opened.assert_called_once_with("rb")
                self.assertEqual(hashlib.sha256(inspected.call_args.args[0]).hexdigest(), result["sha256"])
                if valid:
                    self.assertEqual(result["inventory"]["status"], "observed-structure")
                    self.assertEqual(result["inventory"]["members"]["coll/en.res"]["offset"], 256)
                else:
                    self.assertEqual(result["inventory"], {"status": "unavailable", "reason": "unsupported-package-layout"})

    def test_inventory_exception_text_is_closed(self):
        data = fixture()
        for message, reason in [("prefix-mismatch", "prefix-mismatch"),
                                ("PRIVATE", "unsupported-package-layout")]:
            with patch.object(Path, "open", return_value=io.BytesIO(data)), \
                    patch.object(probe, "PACKAGE_SIZE", len(data)), \
                    patch.object(probe, "PACKAGE_SHA256", hashlib.sha256(data).hexdigest()), \
                    patch.object(probe, "inventory", side_effect=ValueError(message)):
                self.assertEqual(probe.inspect_data_candidate(Path("fixture"))["inventory"],
                                 {"status": "unavailable", "reason": reason})

    def test_actual_prefix_mismatch_is_preserved(self):
        data = fixture().replace(b"icudt72l", b"icudt70l")
        with patch.object(Path, "open", return_value=io.BytesIO(data)), \
                patch.object(probe, "PACKAGE_SIZE", len(data)), \
                patch.object(probe, "PACKAGE_SHA256", hashlib.sha256(data).hexdigest()):
            self.assertEqual(probe.inspect_data_candidate(Path("fixture"))["inventory"],
                             {"status": "unavailable", "reason": "prefix-mismatch"})

    def test_no_raw_error_text(self):
        for error, reason in [(FileNotFoundError("PRIVATE"), "file-not-found"),
                              (PermissionError("PRIVATE"), "access-denied"),
                              (OSError("PRIVATE"), "file-read-error")]:
            with patch.object(Path, "open", side_effect=error):
                self.assertEqual(probe.inspect_data_candidate(Path("PRIVATE")),
                                 {"status": "unavailable", "reason": reason})

    def test_midstream_failure_does_not_publish_partial_digest(self):
        class BrokenStream(io.BytesIO):
            def read(self, length):
                if self.tell():
                    raise OSError("PRIVATE")
                return super().read(length)
        with patch.object(Path, "open", return_value=BrokenStream(b"abcdef")), \
                patch.object(probe, "CHUNK_SIZE", 3):
            self.assertEqual(probe.inspect_data_candidate(Path("PRIVATE")),
                             {"status": "unavailable", "reason": "file-read-error"})


if __name__ == "__main__":
    unittest.main()
