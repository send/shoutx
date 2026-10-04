"""Offline orchestration checks; real boundary semantics have separate tests."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ROWS = [("ubuntu-22.04", "linux-x64", "Linux"),
        ("ubuntu-24.04", "linux-x64", "Linux"),
        ("macos-15", "osx-arm64", "macOS"),
        ("windows-latest", "win-x64", "Windows")]
STUB = r'''
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
base = pathlib.Path(os.environ["FIXTURE_DIR"])
mode = os.environ["FIXTURE_MODE"]
with (base / "events.jsonl").open("a") as f:
    f.write(json.dumps([name, *sys.argv[1:]]) + "\n")
if name == "sleep":
    sys.exit(0)
if name == "gh":
    if "/jobs?" in sys.argv[-1]:
        if mode == "api": sys.exit(1)
        print((base / "jobs.json").read_text())
    else:
        if mode == "annotations": sys.exit(1)
        print("[[{\"page\":1}],[{\"page\":2}]]")
elif name == "curl":
    if mode == "log": sys.exit(1)
    print("synthetic log")
elif name == "python":
    with (base / "calls.jsonl").open("a") as f:
        f.write(json.dumps(sys.argv[1:]) + "\n")
    if mode == "verify": sys.exit(1)
    args = sys.argv
    annotations = pathlib.Path(args[args.index("--annotations") + 1])
    assert json.loads(annotations.read_text()) == [{"page":1},{"page":2}]
    target = pathlib.Path(args[args.index("--evidence") + 1])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"status":"passed"}')
else:
    sys.exit(2)
'''


@unittest.skipUnless(shutil.which("bash") and shutil.which("jq"), "requires bash and jq")
class ResearchOrchestrationTests(unittest.TestCase):
    def run_fixture(self, mode):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            binary = base / "bin"
            binary.mkdir()
            for command in ("gh", "curl", "python", "sleep"):
                path = binary / command
                path.write_text(f"#!{sys.executable}\n" + STUB)
                path.chmod(0o755)
            jobs = [{"name": f"runner-differential ({os_name}, {rid})",
                     "conclusion": "success", "id": 100 + index,
                     "run_attempt": index + 1,
                     "check_run_url": f"https://api.github.com/repos/send/shoutx/check-runs/{200 + index}"}
                    for index, (os_name, rid, _) in enumerate(ROWS)]
            if mode == "missing": jobs.pop()
            if mode == "duplicate": jobs.append(dict(jobs[0]))
            if mode == "failed": jobs[0]["conclusion"] = "failure"
            if mode == "attempt": jobs[0]["run_attempt"] = None
            if mode == "check": jobs[0]["check_run_url"] = "invalid"
            (base / "jobs.json").write_text(json.dumps([{"jobs": jobs[:2]}, {"jobs": jobs[2:]}]))
            env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"],
                       FIXTURE_DIR=str(base), FIXTURE_MODE=mode, GH_REPO="send/shoutx",
                       GH_TOKEN="synthetic", GITHUB_RUN_ID="123", RUNNER_TEMP=str(base))
            result = subprocess.run(["bash", str(ROOT / ".github/scripts/verify-research-boundaries.sh")],
                                    env=env, capture_output=True, timeout=30)
            calls = base / "calls.jsonl"
            reports = list((base / "hosted-boundary-evidence/package-matched").glob("*.json"))
            self.assertEqual(len(reports), 4)
            events = [json.loads(line) for line in (base / "events.jsonl").read_text().splitlines()]
            api_calls = [args for name, *args in events if name == "gh"]
            for args in api_calls:
                self.assertEqual(args[:3], ["api", "--paginate", "--slurp"])
            self.assertEqual(api_calls[0][-1],
                             "repos/send/shoutx/actions/runs/123/jobs?filter=latest&per_page=100")
            if mode == "success":
                self.assertEqual([args[-1] for args in api_calls[1:]],
                                 [f"repos/send/shoutx/check-runs/{200+i}/annotations?per_page=100"
                                  for i in range(4)])
                self.assertEqual([args[-1] for name, *args in events if name == "curl"],
                                 [f"https://api.github.com/repos/send/shoutx/actions/jobs/{100+i}/logs"
                                  for i in range(4)])
            expected_failed = (set() if mode == "success" else
                               {row[0] for row in ROWS} if mode in ("api", "log", "annotations", "verify") else
                               {"windows-latest"} if mode == "missing" else {"ubuntu-22.04"})
            for path in reports:
                self.assertEqual(json.loads(path.read_text())["status"],
                                 "failed" if path.stem in expected_failed else "passed")
            return result.returncode, ([json.loads(line) for line in calls.read_text().splitlines()]
                                       if calls.exists() else [])

    def test_success_all_rows_and_source_attempts(self):
        status, calls = self.run_fixture("success")
        self.assertEqual(status, 0)
        self.assertEqual(len(calls), 4)
        for index, ((os_name, _, runner_os), args) in enumerate(zip(ROWS, calls)):
            self.assertEqual(args[args.index("--os") + 1], runner_os)
            self.assertEqual(args[args.index("--job-id") + 1], str(100 + index))
            self.assertEqual(args[args.index("--source-attempt") + 1], str(index + 1))
            self.assertTrue(args[-1].endswith(f"/package-matched/{os_name}.json"))

    def test_invalid_jobs_and_api_fail_closed(self):
        for mode in ("missing", "duplicate", "failed", "attempt", "check", "api"):
            with self.subTest(mode=mode):
                status, calls = self.run_fixture(mode)
                self.assertNotEqual(status, 0)
                self.assertEqual(len(calls), 0 if mode == "api" else 3)

    def test_exhausted_retries_fail(self):
        for mode in ("log", "annotations", "verify"):
            with self.subTest(mode=mode):
                status, calls = self.run_fixture(mode)
                self.assertNotEqual(status, 0)
                self.assertEqual(len(calls), 24 if mode == "verify" else 0)


if __name__ == "__main__":
    unittest.main()
