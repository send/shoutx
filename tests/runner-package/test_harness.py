"""Offline safety/regression checks for the package evidence harness."""
import importlib.util
import io
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/test-runner-package.py"
spec = importlib.util.spec_from_file_location("runner_package", SCRIPT)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class HarnessTests(unittest.TestCase):
    def test_digest_and_size_must_both_match(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "file"
            path.write_bytes(b"abc")
            sha = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
            harness.verify(path, sha, 3)
            with self.assertRaises(ValueError):
                harness.verify(path, sha, 4)
            with self.assertRaises(ValueError):
                harness.verify(path, "0" * 64, 3)

    def test_only_flat_bin_members_are_selected(self):
        self.assertEqual(harness.bin_name("./bin/core.dll"), "core.dll")
        for path in ("../escape", "/bin/escape", "bin/../escape", "externals/a", "bin/nested/file"):
            self.assertIsNone(harness.bin_name(path))
        for path in ("bin/..", "bin/a\\b", "bin/c:stream"):
            with self.assertRaises(ValueError):
                harness.bin_name(path)

    def test_tar_extracts_regular_files_without_path_interpretation(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            archive = root / "test.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                for name in ("./bin/core.dll", "../escape", "externals/ignored"):
                    entry = tarfile.TarInfo(name)
                    entry.size = 3
                    tar.addfile(entry, io.BytesIO(b"abc"))
            harness.extract_bin(archive, root / "bin")
            self.assertEqual([p.name for p in (root / "bin").iterdir()], ["core.dll"])
            self.assertFalse((root / "escape").exists())
            with self.assertRaises(FileExistsError):
                harness.extract_bin(archive, root / "bin")

    def test_tar_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            archive = root / "test.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                entry = tarfile.TarInfo("bin/link")
                entry.type = tarfile.SYMTYPE
                entry.linkname = "/tmp/escape"
                tar.addfile(entry)
            with self.assertRaises(ValueError):
                harness.extract_bin(archive, root / "bin")

    def test_zip_regular_and_case_collision(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            archive = root / "test.zip"
            with zipfile.ZipFile(archive, "w") as zip_file:
                zip_file.writestr("bin/core.dll", b"abc")
            harness.extract_bin(archive, root / "good")
            self.assertEqual((root / "good/core.dll").read_bytes(), b"abc")
            with zipfile.ZipFile(archive, "a") as zip_file:
                zip_file.writestr("bin/CORE.dll", b"def")
            with self.assertRaises(ValueError):
                harness.extract_bin(archive, root / "bad")

    def test_zip_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            archive = root / "test.zip"
            with zipfile.ZipFile(archive, "w") as zip_file:
                entry = zipfile.ZipInfo("bin/link")
                entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                zip_file.writestr(entry, b"/tmp/escape")
            with self.assertRaises(ValueError):
                harness.extract_bin(archive, root / "bin")

    def test_https_only(self):
        with self.assertRaises(ValueError):
            harness.download("http://example.com/file", Path("unused"), 1)
        with self.assertRaises(ValueError):
            harness.HTTPSRedirect().redirect_request(None, None, 302, "", {}, "http://example.com/")

    def test_host_trace_must_select_package_coreclr(self):
        binary = Path(tempfile.gettempdir()) / "package-bin"
        line = f"CoreCLR path = '{binary / 'libcoreclr.so'}', CoreCLR dir = '{binary}'\n"
        self.assertEqual(harness.verify_coreclr(line, binary, "linux-x64"), "libcoreclr.so")
        for text in ("", line + line, line.replace("package-bin", "sdk-bin")):
            with self.assertRaises(ValueError):
                harness.verify_coreclr(text, binary, "linux-x64")


if __name__ == "__main__":
    unittest.main()
