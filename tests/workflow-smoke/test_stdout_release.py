"""Publication gate fixtures: no network, releases, or candidate code execution."""
import copy
import importlib.util
import io
import json
from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load("gate", ROOT / "scripts/check-stdout-release.py")
fixtures = load("fixtures", Path(__file__).with_name("test_stdout_run.py"))
SHA = fixtures.SHA
REPO = fixtures.REPO


class TransportTests(unittest.TestCase):
    def test_archive_bytes_are_captured_without_terminal_filtering(self):
        payload = b"PK\x03\x04\x1b"
        with patch.object(gate.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=payload)) as run:
            self.assertEqual(gate.request(REPO, "actions/artifacts/123/zip", binary=True), payload)
            self.assertIn("--allow-escape-sequences", run.call_args.args[0])
            self.assertTrue(run.call_args.kwargs["capture_output"])
        with patch.object(gate.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout=b"")):
            with self.assertRaises(ValueError):
                gate.request(REPO, "actions/artifacts/123/zip", binary=True)


def archive(report, name="report.json"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr(name, json.dumps(report))
    return buffer.getvalue()


class GateTests(unittest.TestCase):
    def setUp(self):
        self.source = fixtures.source()
        self.jobs = fixtures.jobs()
        self.trusted = dict(fixtures.source(), id=456, run_attempt=1, head_sha="b" * 40,
                            event="workflow_run", path=".github/workflows/verify-mask-logs.yml")
        self.artifact = {"id": 789, "name": f"stdout-verification-123-2-{SHA}",
                         "expired": False, "size_in_bytes": 10000, "workflow_run": {"id": 456}}
        self.verify_job = {"name": "verify", "run_id": 456, "run_attempt": 1,
                           "status": "completed", "conclusion": "success"}
        self.report = {"schema": 1, "status": "passed", "sourceRepository": REPO,
                       "sourceRunId": 123, "sourceRunAttempt": 2, "sourceHeadSha": SHA,
                       "verifierRunId": 456, "verifierRunAttempt": 1, "verifierSha": "b" * 40,
                       "profile": {}, "ordinary": {}}
        for group, labels in (("profile", gate.verifier.PROFILE), ("ordinary", gate.verifier.ORDINARY)):
            for label in labels:
                system = labels[label][1] if group == "profile" else labels[label][0]
                job_name = (f"test ({label})" if group == "ordinary" else
                            f"runner-differential ({label}, {labels[label][0]})")
                job_id = next(row["id"] for row in self.jobs if row["name"] == job_name)
                image = {"ubuntu-22.04": "ubuntu22", "ubuntu-24.04": "ubuntu24",
                         "macos-15": "macos15", "windows-2025": "win25"}.get(label, "ordinary")
                self.report[group][label] = {"status": "passed", "maskCases": 8, "annotationCases": 30,
                    "jobId": job_id, "logSha256": "c" * 64, "annotationsSha256": "d" * 64,
                    "identity": {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2",
                        "GITHUB_SHA": SHA, "SHOUTX_SOURCE_HEAD": SHA, "RUNNER_OS": system,
                        "RUNNER_ARCH": "ARM64" if label == "macos-15" else "X64", "ImageOS": image}}

    def request(self, repo, path, **kwargs):
        self.assertEqual(repo, REPO)
        routes = {
            f"actions/workflows/ci.yml/runs?head_sha={SHA}&branch=main&per_page=1": {"workflow_runs": [self.source]},
            "actions/runs/123/attempts/2/jobs?per_page=100": [{"jobs": self.jobs}],
            f"actions/artifacts?name=stdout-verification-123-2-{SHA}&per_page=100": [{"artifacts": [self.artifact]}],
            "actions/runs/456": self.trusted,
            "actions/artifacts/789/zip": archive(self.report),
            "actions/runs/456/attempts/1/jobs?per_page=100": [{"jobs": [self.verify_job]}],
            "actions/runs/123": self.source,
        }
        return copy.deepcopy(routes[path])

    def check(self):
        with patch.object(gate, "request", side_effect=self.request):
            return gate.check(REPO, SHA)

    def test_complete_exact_source_is_eligible(self):
        self.assertEqual(self.check()["artifactId"], 789)

    def test_all_identity_and_status_mismatches_block(self):
        for key, value in (("status", "not-exercised"), ("schema", 9),
                           ("sourceRepository", "other/repo"), ("sourceRunId", 124),
                           ("sourceRunAttempt", 1), ("sourceHeadSha", "e" * 40),
                           ("verifierRunId", 999), ("verifierRunAttempt", 2), ("verifierSha", SHA)):
            original = self.report[key]
            self.report[key] = value
            with self.subTest(key=key), self.assertRaises((ValueError, KeyError)):
                self.check()
            self.report[key] = original

    def test_pending_failed_or_untrusted_verifier_blocks(self):
        for key, value in (("status", "in_progress"), ("conclusion", "failure"),
                           ("event", "pull_request"), ("path", ".github/workflows/ci.yml"),
                           ("head_branch", "feature"), ("head_repository", {"full_name": "fork/repo"})):
            original = self.trusted[key]
            self.trusted[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check()
            self.trusted[key] = original

    def test_expired_or_wrong_name_artifact_blocks(self):
        for key, value in (("expired", True), ("size_in_bytes", 0), ("size_in_bytes", gate.LIMIT + 1),
                           ("name", "other")):
            original = self.artifact[key]
            self.artifact[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check()
            self.artifact[key] = original

    def test_missing_and_partial_evidence_blocks(self):
        for group in ("ordinary", "profile"):
            for label in list(self.report[group]):
                value = self.report[group].pop(label)
                with self.assertRaises(ValueError):
                    self.check()
                self.report[group][label] = value
        row = self.report["profile"]["macos-15"]
        for key, value in (("maskCases", 7), ("annotationCases", 29), ("status", "failed"),
                           ("jobId", 999), ("logSha256", "invalid")):
            original = row[key]
            row[key] = value
            with self.assertRaises(ValueError):
                self.check()
            row[key] = original
        row["identity"]["ImageOS"] = "macos26"
        with self.assertRaises(ValueError):
            self.check()

    def test_skipped_verifier_or_policy_cannot_pass(self):
        self.verify_job["conclusion"] = "skipped"
        with self.assertRaises(ValueError):
            self.check()
        self.verify_job["conclusion"] = "success"
        self.jobs[-1]["conclusion"] = "skipped"
        with self.assertRaises(ValueError):
            self.check()

    def test_archive_not_extracted_and_only_expected_member_accepted(self):
        for name in ("../report.json", "/report.json", "report.json/", "script.py"):
            with self.assertRaises(ValueError):
                gate.read_report(archive(self.report, name))
        with self.assertRaises((ValueError, zipfile.BadZipFile)):
            gate.read_report(b"not a zip")
        with self.assertRaises(ValueError):
            gate.read_report(b"x" * (gate.LIMIT + 1))

    def test_both_publication_decisions_invoke_gate(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text()
        metadata = workflow.split("  metadata:\n", 1)[1].split("  build:\n", 1)[0]
        publish = workflow.split("      - name: Publish verified release\n", 1)[1]
        self.assertIn('python3 -B scripts/check-stdout-release.py --sha "$COMMIT_SHA"', metadata)
        self.assertIn('python3 -B scripts/check-stdout-release.py --sha "$GITHUB_SHA"', publish)
        self.assertLess(publish.index("check-stdout-release.py"), publish.index("gh release edit"))

    def test_new_ci_or_verifier_attempt_during_check_blocks(self):
        for mode in ("new-ci", "source-attempt", "verifier-attempt"):
            counts = {}
            def racing_request(repo, path, **kwargs):
                counts[path] = counts.get(path, 0) + 1
                result = self.request(repo, path, **kwargs)
                if mode == "new-ci" and "workflows/ci.yml/runs?" in path and counts[path] == 2:
                    result["workflow_runs"][0]["id"] = 999
                if mode == "source-attempt" and path == "actions/runs/123":
                    result["run_attempt"] = 3
                if mode == "verifier-attempt" and path == "actions/runs/456" and counts[path] == 2:
                    result["run_attempt"] = 2
                return result
            with self.subTest(mode=mode), patch.object(gate, "request", side_effect=racing_request):
                with self.assertRaises(ValueError):
                    gate.check(REPO, SHA)


if __name__ == "__main__":
    unittest.main()
