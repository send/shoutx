import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from contextlib import redirect_stdout
from hosted_log_commands import BEGIN, END, ROWS, emit, expected, verify_log, verify_run


class Verification(unittest.TestCase):
    def test_emit_disables_echo_outside_measured_block(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"RUNNER_DEBUG": "1"}), redirect_stdout(output), \
                patch("hosted_log_commands.subprocess.run", return_value=Mock(returncode=0, stderr=b"")):
            emit("shoutx")
        self.assertEqual(output.getvalue().splitlines(), ["::echo::off", BEGIN, END])

    def test_source_head_is_distinct_from_tested_merge(self):
        jobs = {"total_count": 4, "jobs": [
            {"name": f"log-commands ({row})", "id": index + 1,
             "conclusion": "success", "head_sha": "source", "run_attempt": 2}
            for index, row in enumerate(ROWS)]}
        env = {"GH_REPO": "send/shoutx", "GITHUB_RUN_ID": "123",
               "GITHUB_RUN_ATTEMPT": "2", "GITHUB_SHA": "merge", "SHOUTX_SOURCE_HEAD": "source"}
        raw = "\n".join([BEGIN, *expected(), END]).encode()
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, env), \
                patch("hosted_log_commands.api", return_value=json.dumps(jobs)), \
                patch("hosted_log_commands.download_log", return_value=raw):
            destination = Path(directory) / "report.json"
            verify_run(destination)
            report = json.loads(destination.read_text())
            self.assertEqual((report["testedSha"], report["sourceHead"]), ("merge", "source"))
            self.assertEqual(len(report["jobs"]), 4)
            for field, value in [("head_sha", "merge"), ("run_attempt", 1),
                                 ("conclusion", "failure"), ("name", "unexpected")]:
                changed = copy.deepcopy(jobs)
                changed["jobs"][0][field] = value
                with patch("hosted_log_commands.api", return_value=json.dumps(changed)), \
                        self.assertRaises(RuntimeError):
                    verify_run(destination)

    def test_exact_and_timestamped(self):
        lines = [BEGIN, *expected(), END]
        for prefix in ["", "2026-10-17T00:00:00.000Z "]:
            verify_log("\n".join(prefix + line for line in lines).encode())

    def test_missing_extra_changed_or_disabled_is_not_success(self):
        lines = [BEGIN, *expected(), END]
        for mutation in [lines[1:], lines[:-1], lines + [END],
                         [BEGIN, END], [BEGIN, "::debug::not decoded", END],
                         [BEGIN, *expected(), "##[warning]extra", END],
                         [BEGIN, *[line for line in expected() if not line.startswith("##[debug]")], END],
                         [BEGIN, *expected()[:-1], END]]:
            with self.assertRaises(RuntimeError):
                verify_log("\n".join(mutation).encode())


if __name__ == "__main__":
    unittest.main()
