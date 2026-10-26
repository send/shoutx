"""Secret assignment helper: exact native stdin/argv and failure propagation."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class SecretStdinHelper(unittest.TestCase):
    def test_native_transport(self):
        windows = os.name == "nt"
        shell = shutil.which("pwsh" if windows else "bash")
        self.assertIsNotNone(shell, "native profile shell is required")
        with tempfile.TemporaryDirectory(prefix="shoutx-secret-stdin-") as directory:
            work = Path(directory)
            binary = work / ("sink.exe" if windows else "sink")
            result = subprocess.run(["rustc", "--edition=2024", str(ROOT / "mask_stdin_stub.rs"),
                                     "-o", str(binary)], capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, "stdin stub did not compile")
            source, capture = work / "input.bin", work / "capture.bin"
            base = dict(os.environ, SHOUTX_STUB_SECRET_VARIABLE="1",
                        SHOUTX_STUB_CAPTURE=str(capture), SHOUTX_TEST_BINARY=str(binary),
                        SHOUTX_TEST_INPUT=str(source), SHOUTX_TEST_HELPER=str(
                            ROOT / ("secret-variable-stdin.ps1" if windows
                                    else "secret-variable-stdin.bash")))
            for output, read_only in [(False, False), (True, False), (False, True), (True, True)]:
                env = {k: v for k, v in base.items() if k not in
                       ("SHOUTX_STUB_OUTPUT", "SHOUTX_STUB_READ_ONLY", "SHOUTX_STUB_FAIL")}
                if output:
                    env["SHOUTX_STUB_OUTPUT"] = "1"
                if read_only:
                    env["SHOUTX_STUB_READ_ONLY"] = "1"
                if windows:
                    script = """+$ErrorActionPreference = 'Stop'
. $env:SHOUTX_TEST_HELPER
$stream = [IO.File]::OpenRead($env:SHOUTX_TEST_INPUT)
try {
    Set-ShoutxSecretVariable -Binary $env:SHOUTX_TEST_BINARY -InputStream $stream `
        -Name Credential -Output:([bool]$env:SHOUTX_STUB_OUTPUT) `
        -ReadOnly:([bool]$env:SHOUTX_STUB_READ_ONLY)
} finally { $stream.Dispose() }
"""
                    args = [shell, "-NoProfile", "-NonInteractive", "-Command", script]
                else:
                    flags = ("--output " if output else "") + ("--read-only " if read_only else "")
                    script = ('set -euo pipefail; source "$SHOUTX_TEST_HELPER"; '
                              'set_shoutx_secret_variable "$SHOUTX_TEST_BINARY" '
                              + flags + '-- Credential < "$SHOUTX_TEST_INPUT"')
                    args = [shell, "-c", script]
                # Includes inputs rejected by the writer: transport must not alter them.
                for data in [b"", b"a\r\r\nb\x1ac", "\ufeffα😀 \t%0A;]".encode(),
                             b"\x00\xff", b"x" * 16_384]:
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
