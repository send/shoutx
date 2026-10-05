"""Offline negative controls; live GitHub results remain separate evidence."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import hosted_boundaries as probe


class SafeTextResult(unittest.TextTestResult):
    def _exc_info_to_string(self, err, test):
        # Even a traceback source line or a literal-golden assertion diff can
        # contain legacy workflow syntax. Suppress all exception details here;
        # unittest still identifies the failing test and exits unsuccessfully.
        return "Hosted boundary offline check failed; diagnostic payload suppressed.\n"


class HostedTests(unittest.TestCase):
    def fixture(self):
        identity = {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_SHA": "a" * 40,
                    "SHOUTX_SOURCE_HEAD": "b" * 40,
                    "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "ImageOS": "ubuntu24",
                    "ImageVersion": "20260920.1"}
        lines = ["Current runner version: '2.337.0'", probe.IDENTITY + json.dumps(identity),
                 probe.BEGIN, *probe.expected_block(), probe.END, probe.FINISH]
        return "\n".join("2026-09-30T12:00:00.000Z " + line for line in lines) + "\n"

    def verify(self, raw=None, actual=None):
        return probe.verify(self.fixture() if raw is None else raw,
                            probe.annotations() if actual is None else actual,
                            "Linux", "123", "2", "a" * 40, "b" * 40)

    def test_success_and_bounded_corpus(self):
        report = self.verify()
        self.assertEqual((report["maskCases"], report["annotationCases"]), (8, 30))
        self.assertIsNone(report["workerCulture"])
        self.assertTrue(report["runnerMatchesPin"])
        other = self.verify(self.fixture().replace("'2.337.0'", "'9.9.9'"))
        self.assertFalse(other["runnerMatchesPin"])
        self.assertEqual(probe.STARTS, ("A", ":", "Ω", "ع", "ह", "日", "😀", "𐐀"))
        items = probe.annotations()
        self.assertEqual(items[0], {
            "annotation_level": "notice", "title": "shoutx-boundary-notice-00 :: %,=Ωع😀",
            "message": "A\u0301\u200d👍🏻日本語 %0A shoutx-boundary-notice-00\n##[warning]shoutx-boundary-notice-00 ::error::data",
            "path": "src/hosted-boundary,percent%25-Ωع😀.rs", "start_line": 1,
            "end_line": 1, "start_column": 1, "end_column": 2})
        for severity in ("notice", "warning", "failure"):
            group = [item for item in items if item["annotation_level"] == severity]
            self.assertEqual(len(group), 10)
            self.assertEqual([item["message"][0] for item in group], [*probe.STARTS, "\r", "\n"])

    def test_log_mutations_fail(self):
        raw = self.fixture()
        mutations = [raw.replace(probe.BEGIN, "missing"), raw + probe.END + "\n",
                     raw.replace("_BEGIN***_END", "_BEGINunmasked_END", 1),
                     raw.replace("_BEGIN***_END", "_BEGIN_END", 1),
                     raw.replace("##[notice]A", "##[warning]A", 1),
                     raw.replace("\u0301", "", 1), raw.replace("%0A", "\n", 1),
                     raw.replace(probe.END, "##[warning]injected\n" + probe.END),
                     raw.replace(probe.FINISH, "truncated"),
                     raw.replace("::stop-commands::***", "::stop-commands::raw-token"),
                     raw.replace("::***::", "::wrong::"),
                     raw.replace("Current runner version:", "Unavailable version:"),
                     raw.replace('"ImageVersion": "20260920.1"', '"ImageVersion": null'),
                     raw.replace('"GITHUB_RUN_ATTEMPT": "2"', '"GITHUB_RUN_ATTEMPT": "1"'),
                     raw.replace('"GITHUB_SHA": "' + "a" * 40, '"GITHUB_SHA": "' + "b" * 40)]
        for mutation in mutations:
            with self.subTest(index=mutations.index(mutation)), self.assertRaises(ValueError):
                self.verify(mutation)

    def test_identity_and_order_mutations_fail(self):
        raw = self.fixture()
        identity_line = next(line for line in raw.split("\n") if probe.IDENTITY in line)
        mutations = [raw + identity_line + "\n", raw + "Current runner version: '2.337.0'\n",
                     raw + probe.FINISH + "\n",
                     raw.replace(probe.FINISH, "").replace(probe.BEGIN, probe.FINISH + "\n" + probe.BEGIN),
                     raw.replace('"RUNNER_OS": "Linux"', '"RUNNER_OS": "Windows"'),
                     raw.replace('"GITHUB_RUN_ID": "123"', '"GITHUB_RUN_ID": "456"'),
                     raw.replace('"RUNNER_ARCH": "X64"', '"RUNNER_ARCH": null'),
                     raw.replace('"SHOUTX_SOURCE_HEAD": "' + "b" * 40, '"SHOUTX_SOURCE_HEAD": "' + "c" * 40),
                     raw.replace("MASK_00_", "MASK_SWAP_").replace("MASK_01_", "MASK_00_").replace("MASK_SWAP_", "MASK_01_")]
        for mutation in mutations:
            with self.assertRaises(ValueError):
                self.verify(mutation)

    def test_failure_output_never_contains_payload_or_source(self):
        class Failing(unittest.TestCase):
            def runTest(self):
                self.assertEqual("##[warning]synthetic", "::error::synthetic")
        output = io.StringIO()
        result = unittest.TextTestRunner(stream=output, resultclass=SafeTextResult).run(Failing())
        self.assertFalse(result.wasSuccessful())
        self.assertNotIn("synthetic", output.getvalue())
        self.assertNotIn("##[", output.getvalue())
        self.assertNotIn("::error", output.getvalue())

    def test_literal_log_excerpt_and_untimestamped_continuations(self):
        self.assertEqual(probe.expected_block()[:3], ["::stop-commands::***",
                         "SHOUTX_BOUNDARY_MASK_00_BEGIN***_END", "SHOUTX_BOUNDARY_MASK_01_BEGIN***_END"])
        self.assertEqual(probe.expected_block()[9:12], ["::***::",
                         "##[notice]A\u0301\u200d👍🏻日本語 %0A shoutx-boundary-notice-00",
                         "##[warning]shoutx-boundary-notice-00 ::error::data"])
        raw = self.fixture().replace("2026-09-30T12:00:00.000Z ##[warning]shoutx-boundary-",
                                     "##[warning]shoutx-boundary-")
        self.verify(raw)

    def test_raw_and_encoded_registration_leaks_fail(self):
        for value, marker in probe.mask_values("123", "2", "Linux"):
            self.assertIn(marker, value)
            for leak in (value, value.replace("%", "%25")):
                with self.assertRaises(ValueError):
                    self.verify(self.fixture() + leak)

    def test_annotation_mutations_fail(self):
        original = probe.annotations()
        for actual in (original[1:], original + [original[0]]):
            with self.assertRaises(ValueError):
                self.verify(actual=actual)
        for field in probe.FIELDS:
            actual = copy.deepcopy(original)
            actual[0][field] = None
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify(actual=actual)
        with self.assertRaises(ValueError):
            self.verify(actual=original + [{"message": "shoutx-boundary-mask-injected"}])

    def test_timestamp_and_cr_handling(self):
        self.assertEqual(self.verify("\ufeff" + self.fixture())["runnerVersion"], "2.337.0")
        self.assertEqual(probe.log_lines("\ufeffa\n\ufeffb"), ["a", "\ufeffb"])
        self.assertEqual(probe.log_lines("2026-09-30T00:00:00Z a\r\nb\u2028c\n"),
                         ["a", "b\u2028c", ""])
        self.assertEqual(probe.log_lines("##[notice]\rdata\n"), ["##[notice]\rdata", ""])

    def test_native_stdout_is_not_captured(self):
        with patch.object(probe.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, stderr=b"")
            probe.invoke("binary", "mask", [], "A\u0301")
            run.assert_called_once_with(["binary", "github-actions:mask"],
                                        input=b"A\xcc\x81", stderr=subprocess.PIPE)
            for status, stderr in ((1, b""), (0, b"unexpected")):
                run.return_value = subprocess.CompletedProcess([], status, stderr=stderr)
                with self.assertRaises(ValueError):
                    probe.invoke("binary", "mask", [], "synthetic")

    def test_summary_match_mismatch_and_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            context = {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2",
                       "GITHUB_SHA": "a" * 40, "SHOUTX_SOURCE_HEAD": "b" * 40}
            for label, os_name in (("ubuntu-latest", "Linux"), ("macos-latest", "macOS"),
                                   ("windows-latest", "Windows")):
                report = self.verify()
                report["identity"]["RUNNER_OS"] = os_name
                report["verifierAttempt"] = "2"
                (directory / (label + ".json")).write_text(json.dumps(report))
            text, complete = probe.summarize(directory, context)
            self.assertTrue(complete)
            self.assertEqual(text.count("| MATCH |"), 3)
            target = directory / "windows-latest.json"
            original = json.loads(target.read_text())
            different = {**original, "runnerVersion": "9.9.9", "runnerMatchesPin": False}
            target.write_text(json.dumps(different))
            text, complete = probe.summarize(directory, context)
            self.assertTrue(complete)  # Drift is a visible observation, not a test failure.
            self.assertIn("DIFFERS - review required", text)
            for field, value in (("status", "failed"), ("maskCases", 0), ("verifierAttempt", "1"),
                                 ("runnerMatchesPin", "true"), ("runnerVersion", "<unsafe>|payload")):
                target.write_text(json.dumps({**original, field: value}))
                text, complete = probe.summarize(directory, context)
                self.assertFalse(complete)
                self.assertNotIn("<unsafe>", text)
            target.write_text(json.dumps(original))
            self.assertFalse(probe.summarize(directory, {**context, "GITHUB_SHA": "stale"})[1])
            target.write_text("not json")
            self.assertFalse(probe.summarize(directory, context)[1])
            target.unlink()
            self.assertFalse(probe.summarize(directory, context)[1])

    def test_real_producer_wire_bytes(self):
        if not os.environ.get("UNSTABLE_BINARY"):
            if os.environ.get("GITHUB_ACTIONS"):
                self.fail("CI requires the research binary for wire checks")
            self.skipTest("requires built research binary")
        binary = str(Path(os.environ["UNSTABLE_BINARY"]).resolve())
        data_escape = lambda value: value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        prop_escape = lambda value: data_escape(value).replace(":", "%3A").replace(",", "%2C")
        cases = []
        for value, _ in probe.mask_values("123", "2", "Linux"):
            cases.append((["github-actions:mask"], value, "::add-mask::" + data_escape(value) + "\n"))
        for item in probe.annotations():
            command = "error" if item["annotation_level"] == "failure" else item["annotation_level"]
            file = str(Path(os.environ.get("GITHUB_WORKSPACE", Path.cwd())) / item["path"])
            options = ["--title", item["title"], "--file", file, "--line", str(item["start_line"]),
                       "--end-line", str(item["end_line"]), "--column", "1", "--end-column", "2"]
            header = ("title=" + prop_escape(item["title"]) + ",file=" + prop_escape(file)
                      + f",line={item['start_line']},endLine={item['end_line']},col=1,endColumn=2,")
            cases.append((["github-actions:" + command, *options], item["message"],
                          "::" + command + " " + header + "::" + data_escape(item["message"]) + "\n"))
        for args, value, expected in cases:
            result = subprocess.run([binary, *args], input=value.encode(), capture_output=True)
            # A unittest diff containing legacy syntax is itself executable by
            # Runner. Never include actual/expected payload bytes in a failure.
            self.assertTrue(result.returncode == 0, "producer exit mismatch")
            self.assertTrue(result.stderr == b"", "producer stderr mismatch")
            self.assertTrue(result.stdout == expected.encode(), "producer wire mismatch")


if __name__ == "__main__":
    unittest.main(testRunner=unittest.TextTestRunner(resultclass=SafeTextResult))
