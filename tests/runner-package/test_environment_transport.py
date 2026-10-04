"""Offline child/projection controls; cross-platform package execution is separate."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("observer", HERE / "hosted_worker.py")
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
spec = importlib.util.spec_from_file_location("harness", HERE.parents[1] / "scripts/test-runner-package.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class TransportTests(unittest.TestCase):
    def child(self, mode, value=None, missing_control=False):
        env = {key: value for key, value in os.environ.items()
               if key.upper() not in observer.CONFIGURATION_KEYS}
        env["SHOUTX_TRANSPORT_INHERITANCE_CONTROL"] = "synthetic-inherited"
        if missing_control:
            del env["SHOUTX_TRANSPORT_INHERITANCE_CONTROL"]
        if value is not None:
            env.update(dict.fromkeys(observer.CONFIGURATION_KEYS, value))
        return subprocess.run([sys.executable, "-I", "-S", "environment_transport_child.py", mode],
                              cwd=HERE, env=env, capture_output=True, text=True, timeout=30)

    def test_child_cases_and_verifier(self):
        cases = []
        for mode, value in (("absent", None), ("empty", ""), ("null", ""), ("text", "synthetic-overlay")):
            result = self.child(mode, value)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            self.assertEqual(len(result.stdout.splitlines()), 1)
            cases.append(json.loads(result.stdout))
        report = {"status": "passed", "route": "package-sdk-invoker-to-isolated-python", "cases": cases}
        harness.verify_environment_transport(report)
        for field in report:
            bad = dict(report)
            del bad[field]
            with self.assertRaises(ValueError):
                harness.verify_environment_transport(bad)
        for index in range(4):
            for field in cases[index]:
                bad = json.loads(json.dumps(report))
                del bad["cases"][index][field]
                with self.assertRaises(ValueError):
                    harness.verify_environment_transport(bad)
            for field in ("valuesMatch", "inheritedControlMatches"):
                for value in (False, 1, None):
                    bad = json.loads(json.dumps(report))
                    bad["cases"][index][field] = value
                    with self.assertRaises(ValueError):
                        harness.verify_environment_transport(bad)
            for key in observer.CONFIGURATION_KEYS:
                bad = json.loads(json.dumps(report))
                del bad["cases"][index]["presence"][key]
                with self.assertRaises(ValueError):
                    harness.verify_environment_transport(bad)
                bad["cases"][index]["presence"][key] = "defined" if index == 0 else "absent"
                with self.assertRaises(ValueError):
                    harness.verify_environment_transport(bad)
            bad = json.loads(json.dumps(report))
            bad["cases"][index]["presence"]["unexpected"] = "defined"
            with self.assertRaises(ValueError):
                harness.verify_environment_transport(bad)
        for bad in (None, {}, {**report, "cases": cases[::-1]}, {**report, "cases": cases[:3]},
                    {**report, "cases": [cases[0]] * 4}, {**report, "status": "failed"},
                    {**report, "route": "live-worker"}):
            with self.assertRaises(ValueError):
                harness.verify_environment_transport(bad)
        with self.assertRaises(ValueError):
            harness.verify_environment_transport({**report, "unexpected": True})

    def test_negative_controls_do_not_expose_values(self):
        for mode, value, missing in (("empty", None, False), ("absent", "", False),
                                     ("text", "private-value-control", False), ("empty", "", True)):
            result = self.child(mode, value, missing)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stderr, "")
            self.assertNotIn("private-value-control", result.stdout)
            self.assertNotIn("synthetic-inherited", result.stdout)
            report = json.loads(result.stdout)
            self.assertFalse(report["valuesMatch"] and report["inheritedControlMatches"])

    def test_invalid_mode_is_silent(self):
        result = self.child("unsupported")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (2, "", ""))

    def test_completion_order_and_prior_failure_diagnosis(self):
        for phase, status, exit_code in (("environment-transport", "failed", 1), (None, "passed", 0),
                                         ("collation-observation", "failed", 1)):
            events = []
            record = {"breakRulesSha256": "synthetic"}
            probe = {"status": status, "failedPhase": phase,
                     "loadedManagedAssemblies": [{"file": name} for name in
                                                 ("Runner.Sdk.dll", "System.Diagnostics.Process.dll")]}
            with patch.object(harness, "verify_coverage", side_effect=lambda *args: events.append("coverage")), \
                 patch.object(harness, "verify_collation", side_effect=lambda *args: events.append("collation")):
                with self.assertRaises(ValueError) as error:
                    harness.verify_probe_completion(probe, exit_code, HERE, record)
            if phase == "collation-observation":
                self.assertEqual(str(error.exception), "probe did not pass")
                self.assertEqual(events, [])
                self.assertNotIn("preTransportEvidenceVerified", record)
            else:
                self.assertEqual(str(error.exception), "incomplete environment transport evidence")
                self.assertEqual(events, ["coverage", "collation"])
                self.assertIs(record["preTransportEvidenceVerified"], True)

    def test_completion_success_and_defensive_guards(self):
        transport = {"status": "passed", "route": "package-sdk-invoker-to-isolated-python", "cases": [
            {"case": mode, "presence": dict.fromkeys(observer.CONFIGURATION_KEYS,
                                                    "absent" if mode == "absent" else "defined"),
             "valuesMatch": True, "inheritedControlMatches": True}
            for mode in ("absent", "empty", "null", "text")]}
        for status, exit_code, assemblies, error in (
                ("passed", 0, True, None),
                ("passed", 1, True, "probe did not pass"),
                ("failed", 0, True, "probe did not pass"),
                ("passed", 0, False, "missing environment transport assembly identities")):
            probe = {"status": status, "failedPhase": "environment-transport",
                     "environmentTransport": transport,
                     "loadedManagedAssemblies": [{"file": name} for name in
                         (("Runner.Sdk.dll", "System.Diagnostics.Process.dll") if assemblies else ("Runner.Sdk.dll",))]}
            record = {"breakRulesSha256": "synthetic"}
            with patch.object(harness, "verify_coverage"), patch.object(harness, "verify_collation"):
                if error is None:
                    harness.verify_probe_completion(probe, exit_code, HERE, record)
                else:
                    with self.assertRaisesRegex(ValueError, "^" + error + "$"):
                        harness.verify_probe_completion(probe, exit_code, HERE, record)
            self.assertIs(record["preTransportEvidenceVerified"], True)


if __name__ == "__main__":
    unittest.main()
