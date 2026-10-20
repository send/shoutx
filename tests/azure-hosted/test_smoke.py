import copy
import unittest
import smoke


class SmokeTests(unittest.TestCase):
    def test_variables(self):
        env = {"SHOUTXVALUE": smoke.VALUE, "SHOUTXINJECTION": smoke.INJECTION,
               "SHOUTX_OUTPUT_VALUE": smoke.VALUE, "SHOUTXREADONLY": "fixed"}
        smoke.verify_variables(env)
        for key in env:
            changed = dict(env)
            changed[key] = "wrong"
            with self.assertRaises(RuntimeError):
                smoke.verify_variables(changed)
        with self.assertRaises(RuntimeError):
            smoke.verify_variables(dict(env, SHOUTX_INJECTED="unexpected"))

    def test_timeline_controls(self):
        records = [{"parentId": "job", "attempt": 1, "state": "completed",
                    "name": "shoutx Azure " + severity,
                    "errorCount": int(severity == "error"),
                    "warningCount": int(severity == "warning"),
                    "issues": [{"type": severity, "message": smoke.MESSAGE,
                                "data": {"code": smoke.CODE}}]}
                   for severity in ["warning", "error"]]
        smoke.check_timeline({"records": records}, "job", 1)
        for key, value in [("parentId", "other"), ("attempt", 2), ("state", "pending"),
                           ("issues", []), ("errorCount", 1), ("warningCount", 0)]:
            changed = copy.deepcopy(records)
            changed[0][key] = value
            with self.assertRaises(RuntimeError):
                smoke.check_timeline({"records": changed}, "job", 1)
        for key in ["type", "message", "data"]:
            changed = copy.deepcopy(records)
            changed[0]["issues"][0][key] = {} if key == "data" else "wrong"
            with self.assertRaises(RuntimeError):
                smoke.check_timeline({"records": changed}, "job", 1)
        for changed in [[], records[:1], records + records]:
            with self.assertRaises(RuntimeError):
                smoke.check_timeline({"records": changed}, "job", 1)


if __name__ == "__main__":
    unittest.main()
