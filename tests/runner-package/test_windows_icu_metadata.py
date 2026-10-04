"""Synthetic PE fixtures; no vendor file or real environment required."""
import hashlib
import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import windows_icu_metadata as probe
from test_pe_prefix_digest import fixture as signed_fixture


def fixture():
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 64)
    data[64:68] = b"PE\0\0"
    struct.pack_into("<HHI", data, 68, 0x8664, 1, 0x0ABCDEF1)
    struct.pack_into("<H", data, 84, 112)
    struct.pack_into("<H", data, 88, 0x20B)
    struct.pack_into("<I", data, 144, 0x29E000)
    return data


class MetadataTests(unittest.TestCase):
    def test_prefix_comparison_is_hash_gated_and_failure_preserves_locator(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.dll"
            data = signed_fixture()
            struct.pack_into("<I", data, 144, 0x29E000)
            path.write_bytes(data)
            matching = probe.inspect_file(path, hashlib.sha256(data).hexdigest())
            self.assertEqual(matching["status"], "reference-hash-match")
            self.assertEqual(matching["prefixComparison"]["status"], "available")
            with patch.object(probe, "prefix_digest", side_effect=AssertionError("must not run")):
                self.assertNotIn("prefixComparison", probe.inspect_file(path, "0" * 64))
            with patch.object(probe, "prefix_digest", side_effect=ValueError("PRIVATE")):
                unavailable = probe.inspect_file(path, hashlib.sha256(data).hexdigest())
            self.assertEqual(unavailable["status"], "reference-hash-match")
            self.assertEqual(unavailable["symbolKey"], matching["symbolKey"])
            self.assertEqual(unavailable["prefixComparison"],
                             {"status": "unavailable", "reason": "unsupported-prefix-layout"})
            self.assertNotIn("PRIVATE", json.dumps(unavailable))
            with patch.object(probe, "prefix_digest", side_effect=struct.error("PRIVATE")):
                self.assertEqual(probe.inspect_file(path, hashlib.sha256(data).hexdigest()), unavailable)
            data = fixture()  # Real PE locator succeeds; strict prefix layout does not.
            path.write_bytes(data)
            unsupported = probe.inspect_file(path, hashlib.sha256(data).hexdigest())
            self.assertEqual(unsupported["status"], "reference-hash-match")
            self.assertEqual(unsupported["prefixComparison"],
                             {"status": "unavailable", "reason": "unsupported-prefix-layout"})
            path.write_bytes(b"not PE")
            malformed = probe.inspect_file(path, hashlib.sha256(b"not PE").hexdigest())
            self.assertEqual(malformed["status"], "reference-hash-match-pe-unavailable")
            self.assertNotIn("prefixComparison", malformed)

    def test_key_and_target_gate(self):
        data = fixture()
        self.assertEqual(probe.pe_key(data)["symbolKey"], "0abcdef129e000")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.dll"
            path.write_bytes(data)
            match = probe.inspect_file(path, hashlib.sha256(data).hexdigest())
            self.assertEqual(match["status"], "reference-hash-match")
            mismatch = probe.inspect_file(path, "0" * 64)
            self.assertEqual(mismatch["status"], "candidate-mismatch")
            self.assertNotIn("symbolKey", mismatch)
            self.assertNotIn("timeDateStamp", mismatch)
            with patch.object(probe, "FILE_CAP", 10):
                self.assertEqual(probe.inspect_file(path, "0" * 64),
                                 {"status": "unavailable", "reason": "file-size-limit"})
            with patch.object(probe, "FILE_CAP", len(data)):
                self.assertEqual(probe.inspect_file(path, hashlib.sha256(data).hexdigest()), match)

    def test_malformed_pe(self):
        for offset, fmt, value, reason in [(60, "I", 0, "pe-header"),
                (60, "I", 2**32-1, "pe-header"), (68, "H", 0xAA64, "pe-layout"),
                (70, "H", 0, "pe-layout"), (70, "H", 97, "pe-layout"),
                (84, "H", 111, "pe-layout"), (84, "H", 65535, "pe-bounds"),
                (88, "H", 0x10B, "pe32plus"), (144, "I", 0, "image-size"),
                (144, "I", 2**32-1, "image-size")]:
            data = fixture()
            struct.pack_into("<" + fmt, data, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaisesRegex(ValueError, "^" + reason + "$"):
                probe.pe_key(data)
        for data in [b"", b"MZ", fixture()[:100], b"x" * 512]:
            with self.assertRaises(ValueError):
                probe.pe_key(data)

    def test_reference_and_sanitized_failures(self):
        raw = probe.EVIDENCE.read_bytes()
        expected = probe.reference_digest(raw)
        self.assertEqual(len(expected), 64)
        document = json.loads(raw)
        document["rows"] = []
        with self.assertRaises(ValueError):
            probe.reference_digest(json.dumps(document))
        with patch.object(probe, "system_icu_path", side_effect=OSError("PRIVATE_PATH")):
            report = probe.collect()
        self.assertEqual(report["candidate"], {"status": "unavailable", "reason": "system-api-unavailable"})
        self.assertNotIn("PRIVATE_PATH", json.dumps(report))
        self.assertFalse(report["loadedBytesAttested"])
        self.assertFalse(report["effectiveDataEstablished"])
        for error, reason in [(ValueError("system-directory"), "system-directory"),
                              (ValueError("PRIVATE"), "inspection-error"),
                              (probe.ctypes.ArgumentError("PRIVATE"), "system-api-binding-error")]:
            with patch.object(probe, "system_icu_path", side_effect=error):
                self.assertEqual(probe.collect()["candidate"], {"status": "unavailable", "reason": reason})

    def test_exact_pe_boundary(self):
        self.assertEqual(probe.pe_key(fixture()[:240])["symbolKey"], "0abcdef129e000")
        with self.assertRaisesRegex(ValueError, "^pe-bounds$"):
            probe.pe_key(fixture()[:239])
        data = fixture()
        struct.pack_into("<I", data, 60, len(data) - 24)
        data[-24:] = data[64:88]
        with self.assertRaisesRegex(ValueError, "^pe-bounds$"):
            probe.pe_key(data)

    def test_full_collection_and_preserved_parse_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "PRIVATE_FILE.dll"
            for data, status in [(fixture(), "reference-hash-match"),
                                 (b"PRIVATE_BYTES", "reference-hash-match-pe-unavailable")]:
                path.write_bytes(data)
                digest = hashlib.sha256(data).hexdigest()
                with patch.object(probe, "system_icu_path", return_value=path), \
                        patch.object(probe, "reference_digest", return_value=digest):
                    result = probe.collect()
                self.assertEqual(result["candidate"]["status"], status)
                self.assertEqual(result["candidate"]["sha256"], digest)
                self.assertNotIn("PRIVATE", json.dumps(result))
                if status.endswith("unavailable"):
                    self.assertEqual(result["candidate"]["reason"], "dos-header")
                    self.assertNotIn("symbolKey", result["candidate"])
        self.assertEqual(probe.fixed_reason(ValueError("PRIVATE")), "inspection-error")

    def test_read_failure_reasons(self):
        for error, reason in [(FileNotFoundError("PRIVATE"), "file-not-found"),
                              (PermissionError("PRIVATE"), "access-denied"),
                              (OSError("PRIVATE"), "file-read-error")]:
            with patch.object(Path, "open", side_effect=error):
                self.assertEqual(probe.inspect_file(Path("PRIVATE"), "0" * 64),
                                 {"status": "unavailable", "reason": reason})

    def test_identity_allowlist(self):
        with patch.dict(probe.os.environ, {"SECRET": "PRIVATE", "ImageOS": "::warning::PRIVATE",
                        "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123"}, clear=True):
            self.assertEqual(probe.identity(), {"ImageOS": None, "GITHUB_SHA": "a" * 40,
                                               "GITHUB_RUN_ID": "123"})
        values = {"SHOUTX_SOURCE_HEAD": "b" * 40, "GITHUB_EVENT_NAME": "pull_request",
                  "GITHUB_JOB": "acquisition-locator", "GITHUB_REPOSITORY": "send/shoutx"}
        with patch.dict(probe.os.environ, values, clear=True):
            self.assertEqual(probe.identity(), values)
        for key, value in [("SHOUTX_SOURCE_HEAD", "X" * 40), ("GITHUB_EVENT_NAME", "push"),
                           ("GITHUB_JOB", "a\nb"), ("GITHUB_REPOSITORY", "send/shoutx\n"),
                           ("GITHUB_REPOSITORY", "send/shoutx/extra")]:
            with patch.dict(probe.os.environ, {key: value}, clear=True):
                self.assertEqual(probe.identity(), {key: None})

    def test_reference_rejects_ambiguity_and_bad_digest(self):
        document = json.loads(probe.EVIDENCE.read_bytes())
        row = next(row for row in document["rows"] if row["rid"] == "win-x64")
        document["rows"].append(row)
        with self.assertRaisesRegex(ValueError, "reference-row"):
            probe.reference_digest(json.dumps(document))
        document["rows"].pop()
        module = next(item for item in row["moduleObservation"]["modules"] if item["name"] == "icu.dll")
        module["onDiskSha256"] = "PRIVATE"
        with self.assertRaisesRegex(ValueError, "reference-hash"):
            probe.reference_digest(json.dumps(document))
        row["moduleObservation"]["modules"].append(module)
        with self.assertRaisesRegex(ValueError, "reference-module"):
            probe.reference_digest(json.dumps(document))

    def test_cli_exclusive_output_and_no_raw_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.object(probe.sys, "argv", ["probe", "--output", str(path)]), \
                    patch.object(probe, "collect", return_value={"candidate": {"status": "unavailable"}}), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(probe.main(), 0)
                original = path.read_bytes()
                self.assertEqual(probe.main(), 1)
                self.assertEqual(path.read_bytes(), original)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "ICU acquisition metadata could not be recorded\n")

    def test_native_directory_result_validation(self):
        class Kernel:
            pass
        kernel = Kernel()
        def directory(buffer, size):
            buffer.value = r"C:\Windows\System32"
            return len(buffer.value)
        kernel.GetSystemDirectoryW = directory
        with patch.object(probe.sys, "platform", "win32"), \
                patch.object(probe.ctypes, "sizeof", return_value=8), \
                patch.object(probe.ctypes, "WinDLL", return_value=kernel, create=True):
            self.assertEqual(probe.system_icu_path(), Path(r"C:\Windows\System32") / "icu.dll")
            for size in (0, 32768):
                def invalid(buffer, capacity):
                    return size
                kernel.GetSystemDirectoryW = invalid
                with self.assertRaisesRegex(ValueError, "system-directory"):
                    probe.system_icu_path()
        with patch.object(probe.sys, "platform", "linux"):
            with self.assertRaisesRegex(ValueError, "requires-64-bit-windows"):
                probe.system_icu_path()


if __name__ == "__main__":
    unittest.main()
