import copy
import unittest
from files import cases, check_content, check_identity, check_names, producer


class FileVerifierTests(unittest.TestCase):
    def test_attachment_set_and_content_controls(self):
        for host in ("linux", "windows"):
            for command in ("summary", "uploadfile"):
                expected = [n for cmd, n, _ in cases(host) if cmd == command]
                rows = [{"name": n} for n in expected]
                check_names(rows, expected, host)
                for bad in [rows[:-1], rows + rows[:1], rows + [{"name": "unexpected"}],
                            [{"name": n.replace(command, "wrongtype")} for n in expected]]:
                    with self.assertRaises(RuntimeError):
                        check_names(bad, expected, host)
        check_content(b"exact", b"exact")
        for bad in (b"", b"changed", b"exact\n"):
            with self.assertRaises(RuntimeError):
                check_content(bad, b"exact")

    def test_identity_controls(self):
        current = {"BUILD_BUILDID": "20", "BUILD_SOURCEVERSION": "a" * 40,
                   "SYSTEM_JOBID": "job", "SYSTEM_JOBATTEMPT": "1", "binarySha256": "b" * 64}
        build = {"id": 20, "sourceVersion": "a" * 40}
        check_identity(current, current, build)
        for key in current:
            changed = dict(current, **{key: "wrong"})
            with self.assertRaises(RuntimeError):
                check_identity(changed, current, build)
        for field in build:
            with self.assertRaises(RuntimeError):
                check_identity(current, current, dict(build, **{field: "wrong"}))
        task = {"id": "task", "type": "Task", "name": "Emit file attachments", "parentId": "job",
                "state": "completed", "result": "succeeded", "attempt": 1}
        self.assertEqual(producer({"records": [task]}, current), "task")
        for key, value in [("result", "failed"), ("state", "inProgress"), ("attempt", 2),
                           ("parentId", "wrong"), ("warningCount", 1), ("errorCount", 1),
                           ("issues", [{}])]:
            with self.assertRaises(RuntimeError):
                producer({"records": [dict(task, **{key: value})]}, current)
        for rows in [[], [task, copy.deepcopy(task)]]:
            with self.assertRaises(RuntimeError):
                producer({"records": rows}, current)


if __name__ == "__main__":
    unittest.main()
