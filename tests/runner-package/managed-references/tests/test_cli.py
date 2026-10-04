"""CLI success/failure projection; no vendor assemblies or live process access."""
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOL = Path(sys.argv.pop(1)).resolve()


class CliTests(unittest.TestCase):
    def check_failure(self, arguments, code, message):
        result = subprocess.run(["dotnet", str(TOOL), *arguments], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, code)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, (message + os.linesep).encode())

    def test_usage(self):
        for arguments in ([], ["private-sensitive-fixture", "unexpected"]):
            self.check_failure(arguments, 2, "Usage: ManagedReferences PACKAGE_BIN")

    def test_missing_and_malformed_dependencies(self):
        with tempfile.TemporaryDirectory(prefix="shoutx-metadata-cli-") as temporary:
            self.check_failure([temporary], 1, "Managed reference inventory unavailable.")
            deps = Path(temporary) / "Runner.Worker.deps.json"
            for contents in ("not json", "{}", '{"runtimeTarget":{"name":"missing"},"targets":{}}'):
                deps.write_text(contents, encoding="utf-8")
                self.check_failure([temporary], 1, "Managed reference inventory unavailable.")

    def test_asset_failure_and_success(self):
        with tempfile.TemporaryDirectory(prefix="shoutx-metadata-cli-") as temporary:
            directory = Path(temporary)
            (directory / "Runner.Worker.deps.json").write_text(json.dumps({
                "runtimeTarget": {"name": "fixture"},
                "targets": {"fixture": {"fixture/1": {"runtime": {"Fixture.dll": {}}}}},
            }), encoding="utf-8")
            self.check_failure([temporary], 1, "Managed reference inventory unavailable.")
            asset = directory / "Fixture.dll"
            asset.write_bytes(b"not PE")
            self.check_failure([temporary], 1, "Managed reference inventory unavailable.")
            shutil.copyfile(TOOL, asset)
            result = subprocess.run(["dotnet", str(TOOL), temporary], capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, b"")
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "scanned-member-references")
            self.assertEqual([item["name"] for item in report["assemblies"]], ["Fixture.dll"])


if __name__ == "__main__":
    unittest.main()
