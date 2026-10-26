import copy
import unittest
from metadata import check_metadata, check_producers, expected_tags, values


class MetadataTests(unittest.TestCase):
    def test_effect_and_identity_mutations(self):
        for host in ("linux", "windows"):
            for index in range(4):
                number, _ = values(host, index)
                tags = expected_tags(host, index)
                valid = dict(id=42, sourceVersion="reviewed-sha", buildNumber=number, tags=tags)
                check_metadata(valid, "42", "reviewed-sha", number, tags)
                for key, wrong in [("id", 43), ("sourceVersion", "other"),
                                   ("buildNumber", "unchanged"), ("tags", tags[:-1]),
                                   ("tags", tags + ["extra"]), ("tags", tags + tags[:1]),
                                   ("tags", [tags[0].upper()] + tags[1:]),
                                   ("tags", [" " + tags[0]] + tags[1:]),
                                   ("tags", ["wrong"]), ("tags", None)]:
                    mutated = copy.deepcopy(valid)
                    mutated[key] = wrong
                    with self.assertRaises(RuntimeError):
                        check_metadata(mutated, "42", "reviewed-sha", number, tags)
                for key in valid:
                    mutated = copy.deepcopy(valid)
                    del mutated[key]
                    with self.assertRaises(RuntimeError):
                        check_metadata(mutated, "42", "reviewed-sha", number, tags)

    def test_cap_and_serial_inventory(self):
        for host in ("linux", "windows"):
            for value in values(host, 2):
                self.assertEqual(len(value.encode("utf-16-le")) // 2, 255)
        self.assertEqual(expected_tags("linux", -1), [])
        self.assertEqual(expected_tags("windows", -1), expected_tags("linux", 3))
        self.assertEqual(len(set(expected_tags("windows", 3))), 8)

    def test_producer_task_failures(self):
        record = dict(parentId="job", name="Emit metadata 0", type="Task",
                      state="completed", result="succeeded", errorCount=0, warningCount=0, issues=[])
        check_producers({"records": [record]}, "JOB", 0)
        for key, value in [("parentId", "other"), ("name", "wrong"),
                           ("result", "succeededWithIssues"), ("state", "inProgress"),
                           ("errorCount", 1), ("warningCount", 1), ("issues", [{}])]:
            wrong = dict(record, **{key: value})
            with self.assertRaises(RuntimeError):
                check_producers({"records": [wrong]}, "job", 0)
        for records in [[], [record, record]]:
            with self.assertRaises(RuntimeError):
                check_producers({"records": records}, "job", 0)


if __name__ == "__main__":
    unittest.main()
