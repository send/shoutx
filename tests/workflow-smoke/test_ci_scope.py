"""Exercise the actual CI change detector, including no-diff scheduled runs."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / ".github/scripts/ci-scope.sh"
ROOT = SCRIPT.parents[2]


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "CI fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.base = self.commit("README.md")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.PIPE).decode().strip()

    def commit(self, name):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")
        self.git("add", name)
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def scope(self, event, base="", head=""):
        result = subprocess.run(["bash", str(SCRIPT)], cwd=self.root,
                                env={**os.environ, "EVENT_NAME": event, "BASE_SHA": base, "HEAD_SHA": head},
                                capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        return result.stdout

    def test_explicit_runs_ignore_missing_refs_and_unchanged_tree(self):
        for event in ("schedule", "workflow_dispatch"):
            self.assertEqual(self.scope(event), b"true\n")
            self.assertEqual(self.scope(event, self.base, self.base), b"true\n")

    def test_documentation_only_still_skips(self):
        head = self.commit("docs/fixture.md")
        for event in ("push", "pull_request"):
            self.assertEqual(self.scope(event, self.base, head), b"false\n")

    def test_code_and_workflow_changes_run(self):
        for name in ("src/fixture.rs", ".github/workflows/fixture.yml"):
            head = self.commit(name)
            for event in ("push", "pull_request"):
                self.assertEqual(self.scope(event, self.base, head), b"true\n")

    def test_missing_history_and_initial_push_fail_open_to_full_ci(self):
        for event, base, head in (("push", "0" * 40, self.base), ("push", "missing", self.base),
                                  ("pull_request", "", self.base), ("unknown", "", "")):
            self.assertEqual(self.scope(event, base, head), b"true\n")


class AggregateTests(unittest.TestCase):
    """Execute the actual aggregate shell block, not a copied gate model."""

    def setUp(self):
        self.workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        aggregate = self.workflow.split("  ci-result:\n", 1)[1]
        self.script = textwrap.dedent(aggregate.split("        run: |\n", 1)[1])
        self.always = ("STABLE_DOCS_RESULT", "CHANGES_RESULT", "HOSTED_ANNOTATIONS_RESULT")
        self.full = ("DEPENDENCIES_RESULT", "TEST_RESULT", "MSRV_RESULT",
                     "RUNNER_DIFFERENTIAL_RESULT", "UNICODE_POLICY_RESULT")

    def run_gate(self, full=True, **changes):
        env = {"PATH": os.environ["PATH"], "RUN_CI": "true" if full else "false"}
        env.update({key: "success" for key in self.always})
        env.update({key: "success" if full else "skipped" for key in self.full})
        env.update(changes)
        return subprocess.run(["bash", "-e", "-o", "pipefail", "-c", self.script],
                              env=env, capture_output=True).returncode

    def test_complete_and_docs_only_results(self):
        self.assertEqual(self.run_gate(), 0)
        self.assertEqual(self.run_gate(False), 0)

    def test_incomplete_full_results_fail(self):
        for key in self.always + self.full:
            for status in ("", "failure", "cancelled", "skipped", "pending"):
                with self.subTest(key=key, status=status):
                    self.assertNotEqual(self.run_gate(**{key: status}), 0)

    def test_docs_only_cannot_hide_inconsistent_or_failed_jobs(self):
        for key in self.full:
            for status in ("", "failure", "success"):
                with self.subTest(key=key, status=status):
                    self.assertNotEqual(self.run_gate(False, **{key: status}), 0)
        self.assertNotEqual(self.run_gate(RUN_CI=""), 0)

    def test_policy_in_same_full_ci_and_aggregate(self):
        policy_job = self.workflow.split("  unicode-policy:\n", 1)[1].split("\n  dependencies:", 1)[0]
        self.assertIn("needs: changes", policy_job)
        self.assertIn("if: ${{ needs.changes.outputs.run_ci == 'true' }}", policy_job)
        self.assertIn("uses: ./.github/workflows/unicode-policy.yml", policy_job)
        aggregate = self.workflow.split("  ci-result:\n", 1)[1]
        self.assertRegex(aggregate, r"needs: \[[^\n]*\bunicode-policy\b")
        self.assertIn("UNICODE_POLICY_RESULT: ${{ needs.unicode-policy.result }}", aggregate)
        policy = (ROOT / ".github/workflows/unicode-policy.yml").read_text()
        triggers = policy.split("on:\n", 1)[1].split("\npermissions:", 1)[0]
        self.assertIn("  workflow_call:", triggers)
        self.assertNotRegex(triggers, r"(?m)^  (pull_request|push|schedule|workflow_dispatch):")
        self.assertIn("os: [ubuntu-22.04, ubuntu-24.04, macos-15, windows-2025]", policy)
        profile = self.workflow.split("  runner-differential:\n", 1)[1].split("  hosted-annotations:\n", 1)[0]
        self.assertEqual(re.findall(r"- os: (\S+)", profile),
                         ["ubuntu-22.04", "ubuntu-24.04", "macos-15", "windows-2025"])


if __name__ == "__main__":
    unittest.main()
