"""Independent fixtures for trusted verifier identity, completeness and effects."""
import copy
import importlib.util
import json
import os
from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("verifier", ROOT / "scripts/verify-stdout-run.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
SHA = "a" * 40
REPO = "send/shoutx"


@patch.dict(os.environ, {"GH_TOKEN": "fixture-token"})
class TransportTests(unittest.TestCase):
    def test_log_escape_sequences_are_captured_as_data(self):
        payload = b"\x1b[36mtrusted shell setup\x1b[0m\n"
        with patch.object(verifier.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=payload)) as run:
            self.assertEqual(verifier.api(REPO, "actions/jobs/123/logs", raw=True), payload.decode())
            self.assertEqual(run.call_args.args[0][0], "curl")
            self.assertIn("--fail", run.call_args.args[0])
            self.assertIn("--location", run.call_args.args[0])
            self.assertTrue(run.call_args.kwargs["capture_output"])
        with patch.object(verifier.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout=b"")):
            with self.assertRaises(ValueError):
                verifier.api(REPO, "actions/jobs/123/logs", raw=True)


def source():
    return {"id": 123, "run_attempt": 2, "head_sha": SHA, "event": "push",
            "head_branch": "main", "repository": {"full_name": REPO},
            "head_repository": {"full_name": REPO}, "path": ".github/workflows/ci.yml",
            "status": "completed", "conclusion": "success"}


def jobs():
    names = ["stable-docs", "changes", "dependencies", "msrv", "hosted-annotations", "CI result",
             "test (ubuntu-latest)", "test (macos-latest)", "test (windows-latest)",
             "runner-differential (ubuntu-22.04, linux-x64)",
             "runner-differential (ubuntu-24.04, linux-x64)",
             "runner-differential (macos-15, osx-arm64)",
             "runner-differential (windows-2025, win-x64)",
             "unicode-policy / candidate (ubuntu-22.04)",
             "unicode-policy / candidate (ubuntu-24.04)",
             "unicode-policy / candidate (macos-15)",
             "unicode-policy / candidate (windows-2025)"]
    return [{"id": index + 1, "name": name, "run_id": 123, "run_attempt": 2,
             "head_sha": SHA, "status": "completed", "conclusion": "success",
             "check_run_url": f"https://api.github.com/repos/{REPO}/check-runs/{index+100}"}
            for index, name in enumerate(names)]


class IdentityTests(unittest.TestCase):
    def test_source_identity(self):
        verifier.source_identity(source(), REPO, 123, 2, SHA)
        for key, value in (("id", 124), ("run_attempt", 1), ("head_sha", "b" * 40),
                           ("event", "pull_request"), ("head_branch", "feature"),
                           ("path", ".github/workflows/other.yml"), ("status", "in_progress"),
                           ("conclusion", "failure"), ("head_repository", {"full_name": "fork/shoutx"}),
                           ("repository", {"full_name": "other/shoutx"})):
            run = source()
            run[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                verifier.source_identity(run, REPO, 123, 2, SHA)

    def test_complete_jobs(self):
        self.assertEqual(len(verifier.job_inventory(jobs(), 123, 2, SHA)), 17)

    def test_any_required_job_missing_or_unsuccessful_fails(self):
        for index in range(len(jobs())):
            rows = jobs()
            rows.pop(index)
            with self.subTest(index=index), self.assertRaises((ValueError, KeyError)):
                verifier.job_inventory(rows, 123, 2, SHA)
            for key, value in (("conclusion", "failure"), ("conclusion", "skipped"),
                               ("status", "in_progress"), ("run_attempt", 1),
                               ("run_id", 9), ("head_sha", "b" * 40)):
                rows = jobs()
                rows[index][key] = value
                with self.subTest(index=index, key=key, value=value), self.assertRaises(ValueError):
                    verifier.job_inventory(rows, 123, 2, SHA)

    def test_duplicate_and_extra_matrix_rows_fail(self):
        for name in (jobs()[0]["name"], "test (extra)", "unicode-policy / candidate (extra)",
                     "runner-differential (extra, linux-x64)"):
            rows = jobs()
            row = dict(rows[0], name=name)
            rows.append(row)
            with self.subTest(name=name), self.assertRaises(ValueError):
                verifier.job_inventory(rows, 123, 2, SHA)

    def test_docs_skips_are_not_evidence_and_mixed_results_fail(self):
        rows = [{"name": name, "conclusion": "skipped"} for name in
                ("test", "runner-differential", "unicode-policy")]
        self.assertIsNone(verifier.job_inventory(rows, 123, 2, SHA))
        for broken in (rows[:-1], rows + [jobs()[6]], [dict(rows[0], conclusion="success"), *rows[1:]]):
            with self.assertRaises(ValueError):
                verifier.job_inventory(broken, 123, 2, SHA)

    def test_generation_and_architecture(self):
        rows = [("ubuntu-22.04", "Linux", "X64", "ubuntu22"),
                ("ubuntu-24.04", "Linux", "X64", "ubuntu24"),
                ("macos-15", "macOS", "ARM64", "macos15"),
                ("windows-2025", "Windows", "X64", "win25-vs2026")]
        for label, system, arch, image in rows:
            report = {"identity": {"RUNNER_OS": system, "RUNNER_ARCH": arch, "ImageOS": image}}
            verifier.profile_identity(report, label)
            for key in ("RUNNER_OS", "RUNNER_ARCH", "ImageOS"):
                bad = copy.deepcopy(report)
                bad["identity"][key] = "other"
                with self.subTest(label=label, key=key), self.assertRaises(ValueError):
                    verifier.profile_identity(bad, label)


class EffectsTests(unittest.TestCase):
    def fixture(self, runner_os="Linux", image="ubuntu24", architecture="X64"):
        identity = {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_SHA": SHA,
                    "SHOUTX_SOURCE_HEAD": SHA, "RUNNER_OS": runner_os, "RUNNER_ARCH": architecture,
                    "ImageOS": image, "ImageVersion": "20261006.1"}
        # Consumer-effect corpus already has independent exact-byte tests;
        # this suite checks transport/orchestration and corruption sensitivity.
        lines = ["Current runner version: '2.337.0'", "SHOUTX_HOSTED_IDENTITY=" + json.dumps(identity),
                 verifier.hosted.BEGIN, *verifier.hosted.expected_block(), verifier.hosted.END,
                 verifier.hosted.FINISH]
        return "\n".join(lines), verifier.hosted.annotations()

    def test_real_effect_verifier_and_failures(self):
        raw, annotations = self.fixture()
        job = jobs()[9]
        def run(raw, annotations):
            def api(repo, path, **kwargs):
                return raw if path.endswith("/logs") else [annotations]
            with patch.object(verifier, "api", side_effect=api), patch.object(verifier.time, "sleep"):
                return verifier.verify_job(REPO, job, "Linux", 123, 2, SHA)
        report, _ = run(raw, annotations)
        self.assertEqual(report["maskCases"], 8)
        self.assertEqual(report["annotationCases"], 30)
        marker = next(verifier.hosted.mask_values("123", "2", "Linux"))[1]
        for broken in (raw + marker, raw.replace("SHOUTX_BOUNDARY_MASK_00_BEGIN***_END", "missing"),
                       raw.replace('"GITHUB_RUN_ATTEMPT": "2"', '"GITHUB_RUN_ATTEMPT": "1"'),
                       raw + "shoutx-mask-" + "a" * 32):
            with self.assertRaises(ValueError):
                run(broken, annotations)
        with self.assertRaises(ValueError):
            run(raw, annotations[:-1])

    def test_full_run_and_rerun_race(self):
        def api(repo, path, **kwargs):
            if path.endswith("/jobs?per_page=100"):
                return [{"jobs": jobs()}]
            return source()
        def verify_job(repo, job, runner_os, *args):
            label = next((label for label in verifier.PROFILE if label in job["name"]), None)
            image = {"ubuntu-22.04": "ubuntu22", "ubuntu-24.04": "ubuntu24",
                     "macos-15": "macos15", "windows-2025": "win25"}.get(label, "ordinary")
            report = {"identity": {"RUNNER_OS": runner_os, "RUNNER_ARCH": "ARM64" if label == "macos-15" else "X64", "ImageOS": image}}
            raw = "\n".join(f"SHOUTX_MASK_{value}_BEGIN***_END" for _, values in verifier.ORDINARY.values() for value in values)
            return report, raw
        env = {"GITHUB_SHA": "b" * 40, "GITHUB_RUN_ID": "456", "GITHUB_RUN_ATTEMPT": "1"}
        with patch.dict(os.environ, env), patch.object(verifier, "api", side_effect=api), patch.object(verifier, "verify_job", side_effect=verify_job):
            result = verifier.verify_run(REPO, 123, 2, SHA)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(result["profile"]), 4)
        self.assertEqual(result["sourceRunAttempt"], 2)
        responses = [source(), [{"jobs": jobs()}], dict(source(), run_attempt=3)]
        with patch.dict(os.environ, env), patch.object(verifier, "api", side_effect=responses), patch.object(verifier, "verify_job", side_effect=verify_job):
            with self.assertRaises(ValueError):
                verifier.verify_run(REPO, 123, 2, SHA)


if __name__ == "__main__":
    unittest.main()
