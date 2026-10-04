"""Synthetic diagnostic fixtures: no real credentials or Worker memory access."""
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import hosted_worker as probe

EXPECTED = {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_SHA": "a" * 40,
            "GITHUB_REPOSITORY": "send/shoutx", "GITHUB_JOB": "runner-differential",
            "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "ImageOS": "ubuntu22",
            "ImageVersion": "20260927.309.1", "SHOUTX_SOURCE_HEAD": "b" * 40,
            "SHOUTX_MATRIX_OS": "ubuntu-22.04", "SHOUTX_MATRIX_RID": "linux-x64"}
SECRET = "synthetic-private-value-must-not-appear"


def fixture(culture="en-US"):
    return {"JobName": "__default", "JobId": "12345678-1234-1234-1234-123456789abc",
            "ContextData": {"github": {"t": 2, "d": [
                {"k": key, "v": EXPECTED[name]} for key, name in
                (("run_id", "GITHUB_RUN_ID"), ("run_attempt", "GITHUB_RUN_ATTEMPT"),
                 ("repository", "GITHUB_REPOSITORY"), ("sha", "GITHUB_SHA"))]},
                            "matrix": {"t": 2, "d": [{"k": "os", "v": "ubuntu-22.04"},
                                                        {"k": "runtime", "v": "linux-x64"}]}},
            "Variables": {"system.culture": {"Value": culture, "IsSecret": False},
                          "system.github.job": {"Value": "runner-differential"},
                          "secret": {"Value": SECRET, "IsSecret": True}},
            "Resources": {"Token": SECRET}}


def log(message):
    return "[2026-10-04 05:00:00Z INFO Worker] Job message:\n " + json.dumps(message, indent=2) + "\n"


class HostedWorkerTests(unittest.TestCase):
    def project(self, message):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / "Worker_20261004-050000-utc.log").write_text(log(message), encoding="utf-8")
            return probe.observe_logs(path, EXPECTED)

    def test_only_requested_startup_fields_survive(self):
        for culture in ("", "en-US"):
            with self.subTest(culture=culture):
                result = self.project(fixture(culture))
                self.assertEqual(result, {"timelineJobId": "12345678-1234-1234-1234-123456789abc",
                                         "cultureInput": culture, "cultureInputStatus": "observed",
                                         "startupCulture": None,
                                         "startupCultureStatus": "missing-or-ambiguous"})
                self.assertNotIn(SECRET, json.dumps(result))

    def test_startup_culture_is_separate_and_exact(self):
        prefix = "[2026-10-04 04:59:59Z INFO Worker] Culture: "
        message = fixture()
        del message["Variables"]["system.culture"]
        cases = [(prefix + culture + "\n", culture, "observed") for culture in ("", "en-US")]
        cases += [(prefix + value + "\n", None, "redacted-or-outside-selected-scope")
                  for value in (SECRET, "***", "th-TH", " en-US", "en-US ", " ",
                                "en-us", "en_US", "en-US.UTF-8", "Invariant")]
        cases += [("", None, "missing-or-ambiguous"),
                  ((prefix + "en-US\n") * 2, None, "missing-or-ambiguous"),
                  (prefix + "\n" + prefix + "en-US\n", None, "missing-or-ambiguous"),
                  (prefix.replace("Culture:", "UI Culture:") + "en-US\n", None, "missing-or-ambiguous"),
                  (prefix.replace("INFO Worker", "INFO Listener") + "en-US\n", None, "missing-or-ambiguous"),
                  (prefix.rstrip() + "\n", None, "missing-or-ambiguous"),
                  (" " + prefix + "en-US\n", None, "missing-or-ambiguous"),
                  (prefix.replace("INFO", "WARN") + "en-US\n", None, "missing-or-ambiguous")]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "Worker_20261004-050000-utc.log"
            for newline in ("\n", "\r\n"):
                for before, expected, status in cases:
                    with self.subTest(newline=newline, status=status, before=before):
                        # A later culture-looking line must never be selected.
                        text = before + log(message) + prefix + "en-US\n"
                        path.write_bytes(text.replace("\n", newline).encode())
                        result = probe.observe_logs(directory, EXPECTED)
                        self.assertEqual(result["startupCulture"], expected)
                        self.assertEqual(result["startupCultureStatus"], status)
                        self.assertEqual(result["cultureInputStatus"], "absent")
                        self.assertNotIn(SECRET, json.dumps(result))
            # Startup and job-supplied cultures are independent observations.
            path.write_text(prefix + "\n" + log(fixture("en-US")))
            result = probe.observe_logs(directory, EXPECTED)
            self.assertEqual(result["startupCulture"], "")
            self.assertEqual(result["cultureInput"], "en-US")

    def test_startup_line_framing_and_file_boundary(self):
        prefix = "[2026-10-04 04:59:59Z INFO Worker] Culture: "
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "Worker_20261004-050001-utc.log"
            for value in ("en-US\rX\n", "en-US\r\r\n"):
                path.write_bytes((prefix + value + log(fixture())).encode())
                self.assertEqual(probe.observe_logs(directory, EXPECTED)["startupCultureStatus"],
                                 "missing-or-ambiguous")
            path.write_bytes((prefix + "en-US\r" + log(fixture())).encode())
            with self.assertRaisesRegex(probe.Unavailable, "^missing-or-ambiguous-job-message$"):
                probe.observe_logs(directory, EXPECTED)
            path.write_bytes((prefix + "en-US\r\n" + log(fixture())).encode())
            self.assertEqual(probe.observe_logs(directory, EXPECTED)["startupCulture"], "en-US")
            # Deliberately recognize only the exact source-emitted form.
            path.write_text(prefix.replace("INFO", "VERB") + "en-US\n" + prefix + "\n" + log(fixture()))
            self.assertEqual(probe.observe_logs(directory, EXPECTED)["startupCulture"], "")
            path.write_text(log(fixture()))
            (directory / "Worker_20261004-050000-utc.log").write_text(prefix + "en-US\n")
            (directory / "Runner_20261004-050000-utc.log").write_text(prefix + "en-US\n")
            self.assertEqual(probe.observe_logs(directory, EXPECTED)["startupCultureStatus"],
                             "missing-or-ambiguous")

    def test_unknown_or_secret_culture_not_disclosed(self):
        for value in (SECRET, "***", "th-TH", None):
            self.assertIsNone(self.project(fixture(value))["cultureInput"])
        value = fixture()
        value["Variables"]["system.culture"]["IsSecret"] = True
        self.assertIsNone(self.project(value)["cultureInput"])
        del value["Variables"]["system.culture"]
        self.assertEqual(self.project(value)["cultureInputStatus"], "absent")

    def test_exact_job_context_required(self):
        for index in range(4):
            value = fixture()
            value["ContextData"]["github"]["d"][index]["v"] = "mismatch"
            with self.assertRaises(probe.Unavailable): self.project(value)
        value = fixture()
        value["Variables"]["system.github.job"]["Value"] = "another-job"
        with self.assertRaises(probe.Unavailable): self.project(value)
        value["ContextData"]["github"]["d"].append({"k": "job", "v": "runner-differential"})
        self.assertEqual(self.project(value)["cultureInputStatus"], "observed")
        value["ContextData"]["github"]["d"][-1]["v"] = "incorrect-overlay"
        with self.assertRaises(probe.Unavailable): self.project(value)
        for index in (0, 1):
            value = fixture()
            value["ContextData"]["matrix"]["d"][index]["v"] = "wrong-leg"
            with self.assertRaises(probe.Unavailable): self.project(value)

    def test_duplicate_or_missing_records_and_size_limits(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with self.assertRaisesRegex(probe.Unavailable, "^diagnostic-files-unavailable$"):
                probe.observe_logs(directory, EXPECTED)
            path = directory / "Worker_20261004-050000-utc.log"
            path.write_text(log(fixture()) * 2)
            with self.assertRaisesRegex(probe.Unavailable, "^multiple-job-message-markers$"):
                probe.observe_logs(directory, EXPECTED)
            path.write_text(log(fixture()))
            with patch.object(probe, "FILE_CAP", 10):
                with self.assertRaises(probe.Unavailable): probe.observe_logs(directory, EXPECTED)
            with patch.object(probe, "TOTAL_CAP", 10):
                with self.assertRaises(probe.Unavailable): probe.observe_logs(directory, EXPECTED)
        with self.assertRaises(probe.Unavailable):
            json.loads('{"Variables":{},"variables":{}}', object_pairs_hook=probe.unique_object)
        value = fixture()
        value["ContextData"]["github"]["d"].append({"k": "run_id", "v": "123"})
        with self.assertRaises(probe.Unavailable): self.project(value)

    def test_unix_ancestry_only_pid_and_executable_names(self):
        results = [SimpleNamespace(returncode=0, stdout="20 /usr/bin/python3\n"),
                   SimpleNamespace(returncode=0, stdout="10 /usr/bin/bash\n"),
                   SimpleNamespace(returncode=0, stdout="1 /runner/bin/Runner.Worker\n")]
        with patch.object(probe.platform, "system", return_value="Darwin"), \
                patch.object(probe.os, "getpid", return_value=30), \
                patch.object(probe.subprocess, "run", side_effect=results) as run:
            self.assertEqual(probe.worker_ancestor(), (10, Path("/runner/bin/Runner.Worker")))
            self.assertEqual([call.args[0] for call in run.call_args_list],
                             [["ps", "-p", str(pid), "-o", "ppid=", "-o", "comm="] for pid in (30, 20, 10)])

    def test_main_suppresses_exception_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            with patch.dict(os.environ, EXPECTED, clear=True), \
                    patch.object(probe.sys, "argv", ["probe", "--output", str(path)]), \
                    patch.object(probe, "observe", side_effect=OSError(SECRET)), \
                    patch.object(probe.sys, "stdout", new_callable=io.StringIO) as stdout, \
                    patch.object(probe.sys, "stderr", new_callable=io.StringIO) as stderr:
                self.assertEqual(probe.main(), 0)
                report = path.read_text()
                self.assertEqual(json.loads(report)["status"], "unavailable")
                self.assertNotIn(SECRET, report + stdout.getvalue() + stderr.getvalue())
                self.assertEqual(probe.main(), 1)
                self.assertEqual(path.read_text(), report)

    def test_observe_files_and_partial_unavailable_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "bin"
            binary.mkdir()
            diag = root / "_diag"
            diag.mkdir()
            log_path = diag / "Worker_20261004-050000-utc.log"
            log_path.write_bytes(log(fixture()).replace("\n", "\r\n").encode())
            names = ("Runner.Worker", "Runner.Worker.dll", "Runner.Common.dll", "System.Private.CoreLib.dll",
                     "Runner.Sdk.dll", "Sdk.dll",
                     "Runner.Worker.runtimeconfig.json", "Runner.Worker.deps.json", "libcoreclr.so")
            for name in names: (binary / name).write_bytes(b"synthetic")
            with patch.object(probe, "worker_ancestor", return_value=(10, binary / "Runner.Worker")), \
                    patch.object(probe.platform, "system", return_value="Linux"):
                result = probe.observe(EXPECTED)
                self.assertEqual(result["status"], "observed-job-culture-input")
                self.assertEqual(set(result["onDiskSha256"]), set(names))
                self.assertIsNone(result["processingThreadCulture"])
                self.assertIsNone(result["loadedNativeInputs"])
                (binary / "libcoreclr.so").unlink()
                result = probe.observe(EXPECTED)
                self.assertEqual(result["cultureInput"], "en-US")
                self.assertEqual(result["onDiskIdentityStatus"], "unavailable")
                log_path.write_text(log(fixture(SECRET)))
                self.assertEqual(probe.observe(EXPECTED)["status"], "observed-job-message-without-culture")
                absent = fixture()
                del absent["Variables"]["system.culture"]
                log_path.write_text("[2026-10-04 04:59:59Z INFO Worker] Culture: en-US\n" + log(absent))
                output = root / "report.json"
                with patch.dict(os.environ, EXPECTED, clear=True), \
                        patch.object(probe.sys, "argv", ["probe", "--output", str(output)]):
                    self.assertEqual(probe.main(), 0)
                result = json.loads(output.read_text())
                self.assertEqual(result["schemaVersion"], 2)
                self.assertEqual(result["startupCulture"], "en-US")
                self.assertEqual(result["startupCultureStatus"], "observed")
                self.assertEqual(result["cultureInputStatus"], "absent")
                self.assertEqual(result["status"], "observed-job-message-without-culture")
                self.assertNotIn(SECRET, json.dumps(result))
                (diag / "Worker_20261004-050001-utc.log").write_text(log(fixture()))
                with self.assertRaises(probe.Unavailable): probe.observe(EXPECTED)

    def test_linux_ancestry_resolves_actual_executable(self):
        with patch.object(probe.platform, "system", return_value="Linux"), \
                patch.object(probe.os, "getpid", return_value=30), \
                patch.object(probe.os, "readlink", return_value="/runner/bin/Runner.Worker") as readlink, \
                patch.object(probe.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="1 Runner.Worker\n")):
            self.assertEqual(probe.worker_ancestor(), (30, Path("/runner/bin/Runner.Worker")))
            readlink.assert_called_once_with("/proc/30/exe")

    def test_windows_ancestry_transport_is_allowlisted(self):
        answer = SimpleNamespace(returncode=0, stdout=json.dumps({"pid": 10, "path": "C:/runner/bin/Runner.Worker.exe"}))
        with patch.object(probe.platform, "system", return_value="Windows"), \
                patch.object(probe.os, "getpid", return_value=30), \
                patch.object(probe.subprocess, "run", return_value=answer) as run:
            pid, path = probe.worker_ancestor()
            self.assertEqual(pid, 10)
            self.assertEqual(path, Path("C:/runner/bin/Runner.Worker.exe"))
            self.assertEqual(run.call_args.args[0][:4], ["pwsh", "-NoProfile", "-NonInteractive", "-Command"])
            self.assertNotIn("CommandLine", run.call_args.args[0][-1])
            self.assertEqual(run.call_args.kwargs["env"]["SHOUTX_OBSERVER_PID"], "30")

    def test_invalid_identity_and_unsupported_context(self):
        for name in EXPECTED:
            value = dict(EXPECTED)
            value[name] = None
            with self.assertRaises(probe.Unavailable): probe.identity(value)
        value = fixture()
        value["ContextData"]["github"]["t"] = 5
        with self.assertRaises(probe.Unavailable): self.project(value)

    def test_windows_failures_and_stage_codes(self):
        for answer, reason in ((SimpleNamespace(returncode=1, stdout=SECRET), "worker-ancestry-unavailable"),
                               (SimpleNamespace(returncode=0, stdout=SECRET), "ancestry-unavailable")):
            with patch.object(probe.platform, "system", return_value="Windows"), \
                    patch.object(probe.subprocess, "run", return_value=answer):
                with self.assertRaisesRegex(probe.Unavailable, "^" + reason + "$"):
                    probe.at_stage("ancestry", probe.worker_ancestor)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "Worker_20261004-050000-utc.log"
            other = fixture()
            other["ContextData"]["matrix"]["d"][0]["v"] = "other-leg"
            path.write_text(log(other) + log(fixture()))
            with self.assertRaisesRegex(probe.Unavailable, "^multiple-job-message-markers$"):
                probe.observe_logs(directory, EXPECTED)
            path.write_text("[2026-10-04 05:00:00Z INFO Worker] Job message:\n malformed " + SECRET)
            with self.assertRaisesRegex(probe.Unavailable, "^message-parse-unavailable$"):
                probe.observe_logs(directory, EXPECTED)


if __name__ == "__main__":
    unittest.main()
