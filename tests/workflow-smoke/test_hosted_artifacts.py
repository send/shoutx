import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import hosted_artifacts as probe


class VerificationTests(unittest.TestCase):
    def test_exact_subjects_and_negative_controls(self):
        payload = {"version": 1, "subjects": sorted(probe.expected(), key=lambda x: x["name"])}
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "list.json"
            with patch.dict(os.environ, {"GITHUB_ARTIFACTS_LIST": str(path)}):
                path.write_text(json.dumps(payload), encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()):
                    probe.verify()
                bad_cases = [b"", b"{}", b'{"version":1,"subjects":[]}']
                for field in ["name", "kind", "digest"]:
                    bad = copy.deepcopy(payload)
                    bad["subjects"][0][field] = "wrong"
                    bad_cases.append(json.dumps(bad).encode())
                for delta in [-1, 1]:
                    bad = copy.deepcopy(payload)
                    if delta < 0: bad["subjects"].pop()
                    else: bad["subjects"].append(bad["subjects"][0])
                    bad_cases.append(json.dumps(bad).encode())
                for data in bad_cases:
                    path.write_bytes(data)
                    with self.assertRaises((RuntimeError, ValueError)):
                        probe.verify()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                probe.verify()

    def test_producer_failure_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            environment = {"GITHUB_WORKSPACE": root, "GITHUB_ARTIFACTS": str(Path(root) / "command")}
            with patch.dict(os.environ, environment), patch.object(probe.subprocess, "run") as run:
                run.return_value.returncode = 1
                run.return_value.stderr = b""
                with self.assertRaises(RuntimeError):
                    probe.emit("unused")
                run.return_value.returncode = 0
                run.return_value.stderr = b"unexpected"
                with self.assertRaises(RuntimeError):
                    probe.emit("unused")


if __name__ == "__main__":
    unittest.main()
