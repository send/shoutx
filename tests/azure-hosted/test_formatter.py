"""Offline corruption controls for the completed-log verifier."""
import copy
import json
import unittest

from formatter_cases import expected_blocks
from formatter_verify import check_job


def fixture(mode="on"):
    job = {"id": "job", "name": "linux_" + mode, "type": "Job", "attempt": 1,
           "state": "completed", "result": "succeeded"}
    records = [job, {**job, "id": "emit", "parentId": "job", "type": "Task",
                     "name": "Emit formatter corpus", "log": {"id": 1}},
               {**job, "id": "sentinel", "parentId": "job", "type": "Task",
                "name": "Verify formatter sentinel", "log": {"id": 2}}]
    identity = {"source": "a" * 40, "run": "1", "job": "job", "attempt": "1",
                "agent": "4.test", "image": "ubuntu24", "imageVersion": "test",
                "digest": "b" * 64, "host": "linux", "debug": mode}
    lines = ["SX_FORMATTER_IDENTITY:" + json.dumps(identity), "SX_REJECTIONS_OK"]
    for tag, content in expected_blocks(mode == "on").items():
        lines += [tag + "_BEGIN", *content, tag + "_END"]
    lines += ["SX_AFTER_ALL_GROUPS", "SX_FORMATTER_COMPLETE"]
    logs = {1: ("\n".join(lines) + "\n").encode(), 2: b"SX_SENTINEL_UNCHANGED\n"}
    return job, records, logs


class FormatterVerifierTests(unittest.TestCase):
    def check(self, mode, state, source="a" * 40, run="1"):
        return check_job("linux", mode, *state, source, run)

    def test_distinct_debug_expectations_and_literal_group_data(self):
        self.assertEqual(expected_blocks(True)["SX_DEBUG_escapes"], ["##[debug]%0A%AZP25;]"])
        self.assertEqual(expected_blocks(False)["SX_DEBUG_escapes"], [])
        self.assertEqual(expected_blocks(False)["SX_GROUP_spaces"],
                         ["##[group] \t label \t ", "SX_INSIDE_spaces", "##[endgroup]"])
        for mode in ("on", "off"):
            result = self.check(mode, fixture(mode))
            self.assertEqual(result["producerTask"], "emit")
            self.assertEqual(result["blocks"], 12)

    def test_corrupted_logs_fail(self):
        original = fixture()
        for before, after in [
            (b"##[debug]compile phase", b""),
            (b"##[group]compile phase", b"##[group]changed"),
            (b"##[group]%0A%AZP25;]", b"##[group]%AZP250A%AZP25AZP25%3B%5D"),
            (b"SX_INSIDE_ascii", b"SX_INSIDE_ascii\nextra operation"),
            (b"SX_DEBUG_ascii_BEGIN", b"missing"),
            (b"SX_DEBUG_ascii_END", b"SX_DEBUG_ascii_END\nSX_DEBUG_ascii_END"),
            (b"SX_NESTED_END", b"missing"),
            (b"SX_FORMATTER_COMPLETE", b""),
            (b"SX_REJECTIONS_OK", b""),
            (b'"attempt": "1"', b'"attempt": "2"'),
            (b'"image": "ubuntu24"', b'"image": ""'),
            (b'"digest": "' + b"b" * 64, b'"digest": "invalid'),
        ]:
            state = copy.deepcopy(original)
            self.assertIn(before, state[2][1])
            state[2][1] = state[2][1].replace(before, after, 1)
            with self.subTest(before=before), self.assertRaises((RuntimeError, ValueError)):
                self.check("on", state)
        state = fixture("off")
        state[2][1] = state[2][1].replace(b"SX_DEBUG_empty_BEGIN\n",
                                        b"SX_DEBUG_empty_BEGIN\n##[debug]\n")
        with self.assertRaises(RuntimeError):
            self.check("off", state)

    def test_missing_changed_tasks_and_identity_fail(self):
        for field, value in [("state", "inProgress"), ("result", "failed"),
                             ("warningCount", 1), ("issues", [{}]), ("attempt", 2)]:
            state = fixture()
            state[1][1][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                self.check("on", state)
        for log_id in (1, 2):
            state = fixture()
            del state[2][log_id]
            with self.assertRaises(RuntimeError):
                self.check("on", state)
        for source, run in [("c" * 40, "1"), ("a" * 40, "2")]:
            with self.assertRaises(RuntimeError):
                self.check("on", fixture(), source, run)
        state = fixture()
        state[2][2] = b"SX_SENTINEL_CHANGED\n"
        with self.assertRaises(RuntimeError):
            self.check("on", state)


if __name__ == "__main__":
    unittest.main()
