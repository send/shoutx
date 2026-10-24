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
        for flags in ([], ["--each-line"]):
            result = subprocess.run([binary, "azure-pipelines:mask", *flags],
                                    stdin=slave, capture_output=True, timeout=10)
            assert result.returncode == 2 and not result.stdout
            assert result.stderr == b"error: VALUE omitted while stdin is a terminal\n"
        for flag in ("--help", "--version"):
            result = subprocess.run([binary, "azure-pipelines:mask", flag],
                                    stdin=slave, capture_output=True, timeout=10)
            assert result.returncode == 0 and result.stdout and not result.stderr
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
        for args, expected in [
            (["github-actions:add-matcher"], b"::add-matcher::value\n"),
            (["github-actions:remove-matcher", "file"], b"::remove-matcher::value\n"),
            (["github-actions:remove-matcher", "owner"], b"::remove-matcher owner=value,::\n"),
        ]:
            result = subprocess.run([binary, *args], stdin=slave,
                                    capture_output=True, timeout=10)
            assert result.returncode == 2 and not result.stdout
            assert result.stderr.startswith(b"error: ")
            result = subprocess.run([binary, *args, "value"], stdin=slave,
                                    capture_output=True, timeout=10)
            assert result.returncode == 0 and not result.stderr
            assert result.stdout == expected
    finally:
        os.close(slave)
        os.close(master)
    # A pipe without a reader injects a real native stdout failure. There is no
    # assertion of rollback: these bytes may have been partially written.
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        result = subprocess.run([binary, "azure-pipelines:mask"], input=b"synthetic",
                                stdout=write_end, stderr=subprocess.PIPE, timeout=10)
        assert result.returncode == 1
        assert result.stderr == b"error: failed to write stdout\n"
    finally:
        os.close(write_end)


if __name__ == "__main__":
    verify(sys.argv[1])
