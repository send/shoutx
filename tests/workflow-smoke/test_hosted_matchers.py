import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from hosted_matchers import BEGIN, END, ROWS, CAPACITY_NOTICE, expected_lines, expected_annotations, verify_effects, verify_run


class Verification(unittest.TestCase):
    def annotations(self):
        return [{"annotation_level": "warning", "message": message} for message in expected_annotations()]

    def raw(self, lines=None):
        return "\n".join([BEGIN, *(expected_lines() if lines is None else lines), END]).encode()

    def test_exact_effects(self):
        verify_effects(self.raw(), self.annotations())
        verify_effects(b"\xef\xbb\xbf" + b"\n".join(b"2026-10-17T00:00:00Z " + line
            for line in self.raw().split(b"\n")), self.annotations())

    def test_only_known_infrastructure_notice_is_ignored(self):
        notice = {"annotation_level": "notice", "message": CAPACITY_NOTICE,
                  "path": ".github", "start_line": 1, "end_line": 1}
        verify_effects(self.raw(), [*self.annotations(), notice])
        with self.assertRaises(RuntimeError):
            verify_effects(self.raw(), [*self.annotations()[:-1], notice])
        for key, value in [("annotation_level", "warning"), ("message", "unexpected"),
                           ("start_line", 2), ("path", "other")]:
            with self.assertRaises(RuntimeError):
                verify_effects(self.raw(), [*self.annotations(), {**notice, key: value}])

    def test_disabled_missing_extra_wrong_effects_fail(self):
        for raw in [b"", self.raw([]), self.raw(expected_lines()[:-1]), self.raw() + b"\n" + END.encode(),
                    self.raw().replace(b"##[warning]SHOUTX_MATCH_TARGET:", b"##[warning]"),
                    self.raw([*expected_lines(), "##[warning]extra"]),
                    self.raw([line.replace("##[warning]", "") for line in expected_lines()]),
                    self.raw([line.replace("SHOUTX_MATCH_TARGET:after_owner", "##[warning]after_owner")
                              for line in expected_lines()])]:
            with self.assertRaises(RuntimeError):
                verify_effects(raw, self.annotations())
        for annotations in [[], self.annotations()[:-1], self.annotations() * 2,
                            [{"annotation_level": "error", "message": x} for x in expected_annotations()]]:
            with self.assertRaises(RuntimeError):
                verify_effects(self.raw(), annotations)

    def test_source_run_attempt_and_full_matrix(self):
        jobs = {"total_count": 4, "jobs": [{"name": f"matchers ({row})", "id": i + 1,
            "status": "completed", "conclusion": "success", "head_sha": "source", "run_id": 123,
            "run_attempt": 2, "check_run_url": f"https://api.github.com/repos/send/shoutx/check-runs/{i+1}"}
            for i, row in enumerate(ROWS)]}
        env = {"GH_REPO": "send/shoutx", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2",
               "GITHUB_SHA": "merge", "SHOUTX_SOURCE_HEAD": "source"}
        def api(endpoint):
            return json.dumps(self.annotations() if "/annotations?" in endpoint else jobs)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, env), \
                patch("hosted_matchers.api", side_effect=api), \
                patch("hosted_matchers.download_log", return_value=self.raw()):
            destination = Path(directory) / "report.json"
            verify_run(destination)
            report = json.loads(destination.read_text())
            self.assertEqual((report["sourceHead"], report["testedSha"]), ("source", "merge"))
            self.assertEqual(len(report["jobs"]), 4)
            for field, value in [("head_sha", "merge"), ("run_id", 124), ("run_attempt", 1),
                                 ("conclusion", "failure"), ("name", "missing"),
                                 ("check_run_url", "https://example.com/check-runs/1")]:
                changed = copy.deepcopy(jobs)
                changed["jobs"][0][field] = value
                with patch("hosted_matchers.api", return_value=json.dumps(changed)), self.assertRaises(RuntimeError):
                    verify_run(destination)


if __name__ == "__main__":
    unittest.main()
