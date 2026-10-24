"""Completed-log verifier negative controls, without API access or secrets."""
import copy
import json
import unittest

from mask_cases import blocks, cases
from mask_verify import check_job, log_lines


def fixture(case):
    job = {"id": "job", "name": "linux_" + case.name, "type": "Job",
           "state": "completed", "result": "succeeded", "attempt": 1}
    records = [dict(job, id=str(i), parentId="job", type="Task", name=name, log={"id": i})
               for i, name in enumerate(("Prepare mask fixture", "Register masks", "Emit masked stdout",
                                         "Emit masked stderr", "Calibrate stderr fixture"), 1)]
    identity = {"source": "source", "run": "1", "job": "job", "attempt": "1",
                "case": case.name, "agent": "5.280.0", "image": "ubuntu24",
                "imageVersion": "test", "digest": "a" * 64}
    prepare = ["SX_IDENTITY:" + json.dumps(identity), "SX_PREPARED", "SX_CALIBRATED"]
    calibration = {"OUT": prepare, "ERR": ["SX_CALIBRATED"]}
    emissions = {stream: ["SX_UNRELATED_VISIBLE"] for stream in ("OUT", "ERR")}

    def add(target, tag, payload):
        target.extend([tag + "_BEGIN", *payload, tag + "_END"])

    for stream, tag, expected in blocks(case, True):
        add(emissions[stream], tag, expected)
    for stream in ("OUT", "ERR"):
        emissions[stream].append("SX_EMISSION_COMPLETE")
    if case.each_line:
        for stream in ("OUT", "ERR"):
            add(calibration[stream], "SX_FRAMING_" + stream, ["AA", "", "BB", "", "CC", ""])
    if case.name == "lines_cap":
        prepare.append("SX_REJECTIONS_OK")
    if case.name == "lines_omission":
        for name in ("lines_pem", "lines_mixed", "lines_short", "lines_cap"):
            for stream, tag, expected in blocks(cases()[name], False):
                add(calibration[stream], "CAL_" + name.upper() + "_" + tag, expected)
    logs = {i: ("\n".join(lines) + "\n").encode() for i, lines in
            ((1, prepare), (2, ["SX_REGISTERED"]), (3, emissions["OUT"]),
             (4, emissions["ERR"]), (5, calibration["ERR"]))}
    return job, records, logs


class CompletedLogs(unittest.TestCase):
    def test_positive_and_controls(self):
        for case in cases().values():
            with self.subTest(case=case.name):
                job, records, logs = fixture(case)
                result = check_job(case, job, records, logs, "source", "1")
                self.assertEqual(result["control"], case.control)

    def test_truncation_partial_redaction_wrong_identity_and_operation(self):
        case = cases()["lines_pem"]
        job, records, logs = fixture(case)
        mutations = []
        for changed in [logs[3][:-40], logs[3].replace(b"***", b"**", 1),
                        logs[3].replace(b"***", case.values[0].encode(), 1),
                        logs[3].replace(b"SX_EMISSION_COMPLETE", b""),
                        logs[3].replace(b"SX_OUT_WHOLE_0_END", b"SX_OUT_WHOLE_1_END")]:
            mutations.append({**logs, 3: changed})
        for changed in [logs[1].replace(b'"source": "source"', b'"source": "other"'),
                        logs[1].replace(b'"attempt": "1"', b'"attempt": "2"')]:
            mutations.append({**logs, 1: changed})
        mutations.append({**logs, 2: logs[2] + b"##vso[task.setsecret]synthetic-body-c7a41\n"})
        last = logs[3].rfind(b"***")
        mutations.append({**logs, 3: logs[3][:last] + case.values[-1].encode() + logs[3][last + 3:]})
        mutations.append({**logs, 2: logs[2] + b"##[debug]enabled\n"})
        for changed in mutations:
            with self.assertRaises(RuntimeError):
                check_job(case, job, records, changed, "source", "1")
        changed = copy.deepcopy(records)
        changed[1]["issues"] = [{"type": "warning", "message": "unexpected"}]
        with self.assertRaises(RuntimeError):
            check_job(case, job, changed, logs, "source", "1")
        with self.assertRaises(RuntimeError):
            check_job(case, job, [], {}, "source", "1")
        changed = copy.deepcopy(records)
        changed.append(dict(changed[0], id="extra", name="Unrelated task", log=None))
        with self.assertRaises(RuntimeError):
            check_job(case, job, changed, logs, "source", "1")

    def test_timestamp_removal_does_not_trim_payload(self):
        self.assertEqual(log_lines(b"2026-10-24T01:02:03.1234567Z  \t \r\n"), [" \t ", ""])


if __name__ == "__main__":
    unittest.main()
