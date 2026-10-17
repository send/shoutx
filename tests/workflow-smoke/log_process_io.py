"""POSIX terminal-input contract checks for the native log writers."""
import os
import subprocess
import sys


def verify(binary):
    if os.name != "posix":
        return  # Windows invalid handles are exercised by windows_invalid_handle.c.
    import pty
    master, slave = pty.openpty()
    try:
        for command in ("debug", "group"):
            result = subprocess.run([binary, "github-actions:" + command], stdin=slave,
                                    capture_output=True, timeout=10)
            assert result.returncode == 2 and not result.stdout
            assert result.stderr.startswith(b"error: ")
            result = subprocess.run([binary, "github-actions:" + command, "value"],
                                    stdin=slave, capture_output=True, timeout=10)
            assert result.returncode == 0 and not result.stderr
            assert result.stdout == f"::{command}::value\n".encode()
        result = subprocess.run([binary, "github-actions:endgroup"], stdin=slave,
                                capture_output=True, timeout=10)
        assert result.returncode == 0 and not result.stderr
        assert result.stdout == b"::endgroup::\n"
    finally:
        os.close(slave)
        os.close(master)


if __name__ == "__main__":
    verify(sys.argv[1])
