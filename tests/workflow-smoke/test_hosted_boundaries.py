"""Offline negative controls; live GitHub results remain separate evidence."""
import copy
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import hosted_boundaries as probe


class HostedTests(unittest.TestCase):
    def fixture(self):
        identity = {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_SHA": "a" * 40,
                    "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "ImageOS": "ubuntu24",
                    "ImageVersion": "20260920.1"}
        lines = ["Current runner version: '2.337.0'", probe.IDENTITY + json.dumps(identity),
                 probe.BEGIN, *probe.expected_block(), probe.END]
        return "\n".join("2026-09-30T12:00:00.000Z " + line for line in lines) + "\n"

    def verify(self, raw=None, actual=None):
        return probe.verify(self.fixture() if raw is None else raw,
                            probe.annotations() if actual is None else actual,
                            "Linux", "123", "2", "a" * 40)

    def test_success_and_bounded_corpus(self):
        report = self.verify()
        self.assertEqual((report["maskCases"], report["annotationCases"]), (8, 30))
        self.assertIsNone(report["workerCulture"])
        self.assertEqual(probe.STARTS, ("A", ":", "%", " ", "-", "'", "#", "0"))
        items = probe.annotations()
        self.assertEqual(items[0], {
            "annotation_level": "notice", "title": "shoutx-boundary-notice-00 :: %,=ASCII",
            "message": "A\u0301\u200d👍🏻日本語 %0A shoutx-boundary-notice-00\n##[warning]shoutx-boundary-notice-00 ::error::data",
            "path": "src/hosted-boundary,percent%25-ASCII.rs", "start_line": 1,
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
                     raw.replace("::***::", "::wrong::"),
                     raw.replace("Current runner version:", "Unavailable version:"),
                     raw.replace('"ImageVersion": "20260920.1"', '"ImageVersion": null'),
                     raw.replace('"GITHUB_RUN_ATTEMPT": "2"', '"GITHUB_RUN_ATTEMPT": "1"'),
                     raw.replace('"GITHUB_SHA": "' + "a" * 40, '"GITHUB_SHA": "' + "b" * 40)]
        for mutation in mutations:
            with self.subTest(index=mutations.index(mutation)), self.assertRaises(ValueError):
                self.verify(mutation)

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

    @unittest.skipUnless(os.environ.get("UNSTABLE_BINARY"), "requires built research binary")
    def test_real_producer_wire_bytes(self):
        binary = str(Path(os.environ["UNSTABLE_BINARY"]).resolve())
        data_escape = lambda value: value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        prop_escape = lambda value: data_escape(value).replace(":", "%3A").replace(",", "%2C")
        cases = []
        for value, _ in probe.mask_values("123", "2", "Linux"):
            cases.append((["github-actions:mask"], value, "::add-mask::" + data_escape(value) + "\n"))
        for item in probe.annotations():
            command = "error" if item["annotation_level"] == "failure" else item["annotation_level"]
            options = ["--title", item["title"], "--file", item["path"], "--line", str(item["start_line"]),
                       "--end-line", str(item["end_line"]), "--column", "1", "--end-column", "2"]
            header = ("title=" + prop_escape(item["title"]) + ",file=" + prop_escape(item["path"])
                      + f",line={item['start_line']},endLine={item['end_line']},col=1,endColumn=2")
            cases.append((["github-actions:" + command, *options], item["message"],
                          "::" + command + " " + header + "::" + data_escape(item["message"]) + "\n"))
        for args, value, expected in cases:
            result = subprocess.run([binary, *args], input=value.encode(), capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, b"")
            self.assertEqual(result.stdout, expected.encode())


if __name__ == "__main__":
    unittest.main()
