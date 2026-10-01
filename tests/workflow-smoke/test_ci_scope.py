"""Exercise the actual CI change detector, including no-diff scheduled runs."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / ".github/scripts/ci-scope.sh"


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


if __name__ == "__main__":
    unittest.main()
