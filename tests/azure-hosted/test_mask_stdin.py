"""Native helper byte fidelity and failure propagation; synthetic inputs only."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class StdinHelpers(unittest.TestCase):
    def test_native_shell_stream(self):
        windows = os.name == "nt"
        shell = shutil.which("pwsh" if windows else "bash")
        self.assertIsNotNone(shell, "native profile shell is required")
        with tempfile.TemporaryDirectory(prefix="shoutx-mask-stdin-") as directory:
            work = Path(directory)
            binary = work / ("sink.exe" if windows else "sink")
            build = subprocess.run(["rustc", "--edition=2024", str(ROOT / "mask_stdin_stub.rs"),
                                    "-o", str(binary)], capture_output=True, timeout=120)
            self.assertEqual(build.returncode, 0, "stdin stub did not compile")
            source, capture = work / "input.bin", work / "capture.bin"
            env = dict(os.environ, SHOUTX_STUB_CAPTURE=str(capture),
                       SHOUTX_TEST_BINARY=str(binary), SHOUTX_TEST_INPUT=str(source),
                       SHOUTX_TEST_HELPER=str(ROOT / ("mask-stdin.ps1" if windows
                                                     else "mask-stdin.bash")))
            if windows:
                script = """
 $ErrorActionPreference = 'Stop'
 . $env:SHOUTX_TEST_HELPER
 $stream = [IO.File]::OpenRead($env:SHOUTX_TEST_INPUT)
 try {
   Register-ShoutxMask -Binary $env:SHOUTX_TEST_BINARY -InputStream $stream -EachLine
 } finally { $stream.Dispose() }
 """
                args = [shell, "-NoProfile", "-NonInteractive", "-Command", script]
            else:
                script = 'set -euo pipefail; source "$SHOUTX_TEST_HELPER"; register_shoutx_mask "$SHOUTX_TEST_BINARY" --each-line < "$SHOUTX_TEST_INPUT"'
                args = [shell, "-c", script]
            for data in [b"", b"a\r\nb\rc\n", "\ufeffα😀 \t%0A;]".encode(),
                         b"\x00\xff", b"x" * 1_048_576]:
                source.write_bytes(data)
                result = subprocess.run(args, env=env, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, "helper failed")
                self.assertEqual(result.stdout, b"")
                self.assertEqual(result.stderr, b"")
                self.assertEqual(capture.read_bytes(), data)
            env["SHOUTX_STUB_FAIL"] = "1"
            result = subprocess.run(args, env=env, capture_output=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
