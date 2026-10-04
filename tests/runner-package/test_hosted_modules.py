"""Synthetic metadata fixtures; never read unrelated processes or real secrets."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import hosted_modules as probe
from test_hosted_worker import EXPECTED, SECRET


def mapping(path, permissions="r-xp"):
    return f"1000-2000 {permissions} 00000000 08:01 123 {path}\n"


class ModuleTests(unittest.TestCase):
    def test_linux_selection_deduplication_and_deleted(self):
        raw = (mapping("/usr/lib/libicuuc.so.70.1") * 2 +
               mapping("/runner/bin/libcoreclr.so") +
               mapping("/usr/lib/libicui18n.so.70.1 (deleted)") +
               mapping("/usr/lib/libicudata.so.70.1") +
               mapping("/private/" + SECRET) +
               mapping("/fake/libicuuc.so.70.1.extra") +
               "1000-2000 rw-p 00000000 00:00 0\n").encode()
        self.assertEqual(probe.linux_paths(raw), {
            ("/usr/lib/libicuuc.so.70.1", False), ("/runner/bin/libcoreclr.so", False),
            ("/usr/lib/libicui18n.so.70.1", True), ("/usr/lib/libicudata.so.70.1", False)})
        identities = {}
        probe.linux_paths(mapping("/runner/bin/libcoreclr.so").encode(), identities)
        self.assertEqual(identities, {"/runner/bin/libcoreclr.so": (8, 1, 123)})
        with self.assertRaisesRegex(probe.Unavailable, "ambiguous-mapped-file-identity"):
            probe.linux_paths(mapping("/runner/bin/libcoreclr.so").replace("123", "124").encode(), identities)

    def test_linux_invalid_and_bounded_input(self):
        for path in ("relative/libcoreclr.so", r"/some\040space/libcoreclr.so"):
            with self.assertRaisesRegex(probe.Unavailable, "unsupported-module-path"):
                probe.linux_paths(mapping(path).encode())
        with self.assertRaisesRegex(probe.Unavailable, "unsupported-module-map-record"):
            probe.linux_paths(b"not a mapped region x /libcoreclr.so\n")
        with patch.object(probe, "MAP_CAP", 1):
            with self.assertRaisesRegex(probe.Unavailable, "module-metadata-size-limit"):
                probe.linux_paths(b"xx")
        with self.assertRaisesRegex(probe.Unavailable, "module-metadata-unavailable"):
            probe.at_stage("module-metadata", probe.linux_paths, b"\xff")

    @unittest.skipUnless(hasattr(os, "major"), "POSIX device identity fixture")
    def test_shims_and_linux_identity_handoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "libSystem.Globalization.Native.so"
            path.write_bytes(b"synthetic-shim")
            info = path.stat()
            raw = (f"1000-2000 r-xp 00000000 {os.major(info.st_dev):x}:{os.minor(info.st_dev):x} "
                   f"{info.st_ino} {path}\n").encode()
            real_open = Path.open
            def opened(candidate, *args, **kwargs):
                if str(candidate) == "/proc/123/maps":
                    return io.BytesIO(raw)
                return real_open(candidate, *args, **kwargs)
            with patch.object(probe, "worker_ancestor", return_value=(123, Path(temporary) / "Runner.Worker")), \
                    patch.object(probe.platform, "system", return_value="Linux"), \
                    patch.object(Path, "open", opened):
                result = probe.observe()
            self.assertEqual(result["selectedClasses"]["globalizationShim"], "observed")
            self.assertEqual(result["modules"][0]["mappedFileIdentityStatus"], "matched")
        self.assertEqual(probe.mac_paths(
            b"p123\nftxt\nn/runner/bin/libSystem.Globalization.Native.dylib\n",
            Path("/runner/bin"), 123), {("/runner/bin/libSystem.Globalization.Native.dylib", False)})
        with patch.object(probe.subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps([r"C:\runner\system.globalization.native.dll"]).encode())):
            self.assertEqual(probe.module_paths(123, Path("/runner/bin"), "Windows"),
                             {(r"C:\runner\system.globalization.native.dll", False)})

    def test_macos_exact_paths_and_process(self):
        binary = Path("/runner/bin")
        core = str(binary / "libcoreclr.dylib")
        raw = (f"p123\nn{core}\n"
               "n/usr/lib/libicucore.A.dylib\n"
               "n/elsewhere/libcoreclr.dylib\n"
               "n/elsewhere/libicucore.A.dylib\n" + SECRET)
        self.assertEqual(probe.mac_paths(raw.encode(), binary, 123),
                         {(core, False), ("/usr/lib/libicucore.A.dylib", False)})
        self.assertEqual(probe.mac_paths(b"p123\nn/unselected\n", binary, 123), set())
        with self.assertRaisesRegex(probe.Unavailable, "unexpected-module-process"):
            probe.mac_paths(b"p124\nn/usr/lib/libicucore.A.dylib\n", binary, 123)
        with patch.object(probe, "MAP_CAP", 1):
            with self.assertRaises(probe.Unavailable): probe.mac_paths(b"xx", binary, 123)

    def test_native_transport_selects_only_target_pid(self):
        result = SimpleNamespace(returncode=0, stdout=b"p123\n")
        with patch.object(probe.subprocess, "run", return_value=result) as run:
            self.assertEqual(probe.module_paths(123, Path("/runner/bin"), "Darwin"), set())
            self.assertEqual(run.call_args.args[0], ["/usr/sbin/lsof", "-nP", "-a", "-p", "123", "-d", "txt", "-Fn"])
            self.assertEqual(run.call_args.kwargs["timeout"], 30)
            result.stdout = json.dumps([r"C:\runner\bin\coreclr.dll", r"C:\Windows\System32\icu.dll"]).encode()
            self.assertEqual(len(probe.module_paths(123, Path("/runner/bin"), "Windows")), 2)
            self.assertEqual(run.call_args.kwargs["env"]["SHOUTX_MODULE_PID"], "123")
            self.assertEqual(run.call_args.args[0][:4], ["pwsh", "-NoProfile", "-NonInteractive", "-Command"])
            script = run.call_args.args[0][-1]
            self.assertNotIn("CommandLine", script)
            self.assertIn(".Modules", script)
            self.assertIn(".ModuleName.ToLowerInvariant() -in", script)

    def test_windows_rejects_unexpected_outputs_and_network_paths(self):
        for value in ({"path": SECRET}, [SECRET], [r"relative\icu.dll"],
                      [r"\\server\share\icu.dll"], [r"C:\private\secret.dll"],
                      [r"\\?\C:\icu.dll"], ["C:icu.dll"], ["//server/share/icu.dll"],
                      [r"C:\icu.dll"] * 65, [None]):
            with patch.object(probe.subprocess, "run", return_value=SimpleNamespace(
                    returncode=0, stdout=json.dumps(value).encode())):
                with self.assertRaisesRegex(probe.Unavailable, "unsupported-module-result"):
                    probe.module_paths(123, Path("/runner/bin"), "Windows")
        for answer in (SimpleNamespace(returncode=1, stdout=SECRET.encode()),
                       SimpleNamespace(returncode=0, stdout=b"not-json")):
            with patch.object(probe.subprocess, "run", return_value=answer):
                with self.assertRaises(probe.Unavailable):
                    probe.at_stage("module-metadata", probe.module_paths, 123, Path("/runner/bin"), "Windows")
        with patch.object(probe.subprocess, "run", side_effect=subprocess.TimeoutExpired(SECRET, 30)):
            with self.assertRaisesRegex(probe.Unavailable, "^module-metadata-unavailable$"):
                probe.at_stage("module-metadata", probe.module_paths, 123, Path("/runner/bin"), "Darwin")

    def test_disk_hash_missing_deleted_and_size_cap(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "libcoreclr.so"
            self.assertEqual(probe.disk_hash(path, False)["onDiskStatus"], "unavailable")
            path.write_bytes(b"synthetic-library")
            self.assertEqual(probe.disk_hash(path, False), {"onDiskStatus": "observed",
                             "onDiskSha256": hashlib.sha256(b"synthetic-library").hexdigest(),
                             "mappedFileIdentityStatus": "not-observed"})
            with patch.object(probe.os, "open", side_effect=AssertionError("must not reopen deleted file")):
                self.assertEqual(probe.disk_hash(path, True)["onDiskStatus"], "mapped-path-deleted")
            with patch.object(probe, "FILE_CAP", 1):
                result = probe.disk_hash(path, False)
                self.assertEqual(result["onDiskStatus"], "unavailable")
                self.assertEqual(result["reason"], "unsupported-module-file")

    def test_projection_has_no_raw_paths_and_rechecks_ancestry(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary)
            path = binary / "libcoreclr.so"
            path.write_bytes(b"synthetic")
            ancestor = (123, binary / "Runner.Worker")
            with patch.object(probe, "worker_ancestor", return_value=ancestor) as ancestry, \
                    patch.object(probe.platform, "system", return_value="Linux"), \
                    patch.object(probe, "module_paths", return_value={(str(path), False)}):
                result = probe.observe()
                self.assertEqual(result["status"], "observed-module-metadata")
                self.assertEqual(ancestry.call_count, 2)
                self.assertEqual(result["modules"][0]["name"], "libcoreclr.so")
                self.assertNotIn(temporary, json.dumps(result))
                self.assertIsNone(result["activeBackend"])
                self.assertIsNone(result["effectiveData"])
                self.assertFalse(result["loadedBytesAttested"])
                self.assertEqual(result["selectedClasses"]["coreclr"], "observed")
                self.assertEqual(result["selectedClasses"]["icuCommon"], "not-observed")
                ancestry.side_effect = [ancestor, (124, ancestor[1])]
                with self.assertRaisesRegex(probe.Unavailable, "worker-ancestry-changed"):
                    probe.observe()

    def test_empty_and_duplicate_name_are_unknown(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "Runner.Worker"
            with patch.object(probe, "worker_ancestor", return_value=(123, executable)), \
                    patch.object(probe.platform, "system", return_value="Linux"):
                for paths in (set(), {("/one/libcoreclr.so", False), ("/two/libcoreclr.so", False)},
                              {("/one/libcoreclr.so", False), ("/one/libcoreclr.so", True)},
                              {(f"/lib/libicuuc.so.{index}", False) for index in range(17)}):
                    with patch.object(probe, "module_paths", return_value=paths):
                        with self.assertRaises(probe.Unavailable): probe.observe()

    def test_windows_projection_and_partial_hash_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "Runner.Worker.exe"
            with patch.object(probe, "worker_ancestor", return_value=(123, executable)), \
                    patch.object(probe.platform, "system", return_value="Windows"), \
                    patch.object(probe, "module_paths", return_value={
                        (r"C:\private-directory\icu.dll", False), (r"D:\another-directory\coreclr.dll", False)}), \
                    patch.object(probe, "disk_hash", side_effect=lambda path, *_: {
                        "onDiskStatus": "unavailable" if path.endswith("icu.dll") else "observed",
                        "onDiskSha256": None if path.endswith("icu.dll") else "a" * 64}):
                result = probe.observe()
                self.assertEqual([m["name"] for m in result["modules"]], ["coreclr.dll", "icu.dll"])
                self.assertEqual(result["modules"][1]["onDiskStatus"], "unavailable")
                self.assertNotIn("directory", json.dumps(result))
                self.assertEqual(result["selectedClasses"]["icu.dll"], "observed")
                output = Path(temporary) / "report.json"
                with patch.dict(os.environ, EXPECTED, clear=True), \
                        patch.object(probe.sys, "argv", ["probe", "--output", str(output)]):
                    self.assertEqual(probe.main(), 0)
                self.assertEqual(json.loads(output.read_text())["modules"], result["modules"])

    def test_disk_file_failures_are_independent_statuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "coreclr"
            path.write_bytes(b"synthetic")
            with patch.object(probe.os, "open", side_effect=PermissionError(SECRET)):
                self.assertEqual(probe.disk_hash(path, False)["onDiskStatus"], "unavailable")
            before = path.stat()
            after = SimpleNamespace(st_size=before.st_size + 1, st_mtime_ns=before.st_mtime_ns)
            with patch.object(probe.os, "fstat", side_effect=[before, after]):
                self.assertEqual(probe.disk_hash(path, False)["reason"], "module-file-changed-during-read")
            after = SimpleNamespace(st_size=before.st_size, st_mtime_ns=before.st_mtime_ns + 1)
            with patch.object(probe.os, "fstat", side_effect=[before, after]):
                self.assertEqual(probe.disk_hash(path, False)["reason"], "module-file-changed-during-read")
            if hasattr(os, "major"):
                file_id = (os.major(before.st_dev), os.minor(before.st_dev), before.st_ino)
                self.assertEqual(probe.disk_hash(path, False, file_id)["mappedFileIdentityStatus"], "matched")
                self.assertEqual(probe.disk_hash(path, False, (*file_id[:2], 0))["reason"],
                                 "module-file-identity-mismatch")
                self.assertEqual(probe.disk_hash(path, False, (*file_id[:2], file_id[2] + 1))["reason"],
                                 "module-file-identity-mismatch")
            self.assertEqual(probe.disk_hash(temporary, False)["onDiskStatus"], "unavailable")
            if hasattr(os, "mkfifo"):
                fifo = Path(temporary) / "fifo"
                os.mkfifo(fifo)
                self.assertEqual(probe.disk_hash(fifo, False)["onDiskStatus"], "unavailable")

    def test_transport_failure_platform_and_fixed_main_reason(self):
        with patch.object(probe.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout=SECRET.encode())):
            with self.assertRaisesRegex(probe.Unavailable, "module-metadata-unavailable"):
                probe.module_paths(123, Path("/runner/bin"), "Darwin")
        with self.assertRaisesRegex(probe.Unavailable, "unsupported-module-platform"):
            probe.module_paths(123, Path("/runner/bin"), "other")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "report.json"
            with patch.dict(os.environ, EXPECTED, clear=True), \
                    patch.object(probe.sys, "argv", ["probe", "--output", str(output)]), \
                    patch.object(probe, "observe", side_effect=probe.Unavailable("module-metadata-unavailable")):
                self.assertEqual(probe.main(), 0)
            self.assertEqual(json.loads(output.read_text())["reason"], "module-metadata-unavailable")

    def test_main_suppresses_errors_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "report.json"
            with patch.dict(os.environ, EXPECTED, clear=True), \
                    patch.object(probe.sys, "argv", ["probe", "--output", str(output)]), \
                    patch.object(probe, "observe", side_effect=OSError(SECRET)), \
                    patch.object(probe.sys, "stdout", new_callable=io.StringIO) as stdout, \
                    patch.object(probe.sys, "stderr", new_callable=io.StringIO) as stderr:
                self.assertEqual(probe.main(), 0)
                raw = output.read_text()
                self.assertEqual(json.loads(raw)["status"], "unavailable")
                self.assertNotIn(SECRET, raw + stdout.getvalue() + stderr.getvalue())
                self.assertEqual(probe.main(), 1)
                self.assertEqual(output.read_text(), raw)


if __name__ == "__main__":
    unittest.main()
