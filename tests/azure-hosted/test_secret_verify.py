"""Offline acceptance and discriminating mutations for secret-variable effects."""
import copy
import json
import os
import unittest
from unittest.mock import patch

from secret_cases import (ALL_JOBS, SAME_JOB, SENTINEL, assignments, expected_blocks,
                          CONTROL_PLAIN, CONTROL_OMITTED)
from secret_producer import consume, unmapped
from secret_verify import (attach_task_metadata, check_inventory, check_job,
                           READONLY_ISSUE, MASKED_REJECTION_COMMAND)


def fixture(case):
    job = {"id": "job", "name": "linux_" + case, "type": "Job", "attempt": 1,
           "state": "completed", "result": "succeededWithIssues" if case == "control" else "succeeded"}
    identity = {"source": "source", "run": "1", "job": "job", "attempt": "1",
                "case": case, "agent": "5.280.0", "image": "ubuntu24",
                "imageVersion": "test", "digest": "a" * 64}
    phases = {"Prepare secret fixture": ["SV_IDENTITY:" + json.dumps(identity), "SV_PREPARED"]}

    def block(lines, tag, payload):
        lines.extend([tag + "_BEGIN", *payload, tag + "_END"])

    for index in range(len(assignments(case))):
        if case not in ("dependent", "stage"):
            phases[f"Register {index}"] = [f"SV_REGISTERED_{index}"]
        phases[f"Unmapped {index}"] = [f"SV_UNMAPPED_{index}_OK"]
        for stream in ("OUT", "ERR"):
            lines = [f"SV_CONSUMED_{index}_{stream}_OK"]
            for tag, payload in expected_blocks(case, index, stream, True):
                block(lines, tag, payload)
            phases[f"Consume {index} {stream}"] = lines
    if case in ("size", "control"):
        phases["Prepare secret fixture"].append("SV_REJECTIONS_OK")
    if case == "control":
        for stream in ("OUT", "ERR"):
            lines = ["SV_CALIBRATED_" + stream]
            for target in (*SAME_JOB, "output"):
                for index in range(len(assignments(target))):
                    for tag, payload in expected_blocks(target, index, stream, False):
                        block(lines, "CAL_" + tag, payload)
            phases["Calibrate " + stream] = lines
        phases["Control plain"] = ["SV_PLAIN_REGISTERED"]
        phases["Control plain-check"] = ["SV_PLAIN_BEGIN", CONTROL_PLAIN, "SV_PLAIN_END"]
        phases["Control wrong"] = ["SV_WRONG_REGISTERED"]
        lines = []
        for tag in ("SV_OMISSION", "SV_WRONG"):
            block(lines, tag, [CONTROL_OMITTED])
        phases["Control omission-check"] = lines
        phases["Expected readonly rejection"] = ["SV_OVERWRITE_REQUESTED"]
        phases["Readonly followup"] = ["SV_READONLY_UNCHANGED"]
        for stream in ("OUT", "ERR"):
            for form in ("RAW", "WIRE"):
                block(phases["Readonly followup"], "SV_REJECTED_" + stream + "_" + form, ["***"])
    records, logs = [], {}
    for index, (name, lines) in enumerate(phases.items(), 1):
        record = {"id": str(index), "parentId": "job", "type": "Task", "name": name,
                  "state": "completed", "result": "succeeded", "attempt": 1, "log": {"id": index}}
        if name == "Expected readonly rejection":
            record["issues"] = [{"type": "error", "message": READONLY_ISSUE},
                                {"type": "error", "message": "Unable to process command '" + MASKED_REJECTION_COMMAND}]
            lines.append("##[error]Unable to process command '" + MASKED_REJECTION_COMMAND)
            record["result"] = "succeededWithIssues"
        if case == "output" and name.startswith("Register "):
            item = assignments(case)[int(name.split()[1])]
            record["variables"] = {item.name: {"value": item.value, "isSecret": True}}
        records.append(record)
        logs[index] = ("\n".join(lines) + "\n").encode()
    return job, records, logs


class SecretAdmission(unittest.TestCase):
    def test_exact_job_inventory(self):
        jobs = [{"type": "Job", "name": platform + "_" + case}
                for platform in ("linux", "windows") for case in ALL_JOBS]
        jobs.append({"type": "Job", "name": "verify_secrets"})
        check_inventory(jobs)
        for changed in (jobs[:-1], jobs + [jobs[0]], jobs[:-1] + [{"type": "Job", "name": "unexpected"}]):
            with self.assertRaises(RuntimeError):
                check_inventory(changed)

    def test_all_jobs(self):
        self.assertEqual(len(ALL_JOBS) * 2 + 1, 21)
        for case in ALL_JOBS:
            with self.subTest(case=case):
                result = check_job(case, *fixture(case), "source", "1")
                self.assertEqual(result["case"], case)

    def test_log_mutations(self):
        for case in ("ordinary", "output", "dependent", "stage", "size"):
            job, records, logs = fixture(case)
            consume_id = next(r["log"]["id"] for r in records if r["name"] == "Consume 0 OUT")
            for payload in [logs[consume_id][:-20],
                            logs[consume_id].replace(b"***", b"**", 1),
                            logs[consume_id].replace(b"***", assignments(case)[0].value.encode(), 1),
                            logs[consume_id] + b"##vso[task.setvariable variable=Extra;]x\n",
                            logs[consume_id].replace(b"SV_CONSUMED", b"SV_MISSING")]:
                with self.subTest(case=case), self.assertRaises(RuntimeError):
                    check_job(case, job, records, {**logs, consume_id: payload}, "source", "1")
            for field, value in [("source", "wrong"), ("job", "wrong"), ("attempt", "2")]:
                altered = logs[1].replace(f'"{field}": "{dict(source="source",job="job",attempt="1")[field]}"'.encode(),
                                          f'"{field}": "{value}"'.encode())
                with self.assertRaises(RuntimeError):
                    check_job(case, job, records, {**logs, 1: altered}, "source", "1")
            changed = copy.deepcopy(records)
            changed[0]["issues"] = [{"type": "warning", "message": "unexpected"}]
            with self.assertRaises(RuntimeError):
                check_job(case, job, changed, logs, "source", "1")

    def test_readonly_aggregate_copy(self):
        job, records, logs = fixture("control")
        rejection = next(r for r in records if r["name"] == "Expected readonly rejection")
        error = next(line for line in logs[rejection["log"]["id"]].splitlines()
                     if b"##vso[task.setvariable " in line)
        job["log"] = {"id": 1000}
        logs[1000] = error + b"\n"
        check_job("control", job, records, logs, "source", "1")
        for changed in (b"changed prefix " + error + b"\n",
                        error.replace(b"***", b"visible") + b"\n",
                        error + b"\n##vso[task.setvariable variable=Extra;]x\n"):
            with self.assertRaises(RuntimeError):
                check_job("control", job, records, {**logs, 1000: changed}, "source", "1")
        consume = next(r for r in records if r["name"] == "Consume 0 OUT")
        with self.assertRaises(RuntimeError):
            check_job("control", job, records,
                      {**logs, consume["log"]["id"]: logs[consume["log"]["id"]] + error + b"\n"},
                      "source", "1")

    def test_output_flags_data_and_missing_consumers(self):
        job, records, logs = fixture("output")
        redacted = copy.deepcopy(records)
        for record in redacted:
            for variable in record.get("variables", {}).values():
                variable["value"] = None
        check_job("output", job, redacted, logs, "source", "1")
        for variable in [{"value": assignments("output")[0].value, "isSecret": False},
                         {"value": "changed", "isSecret": True},
                         {"value": assignments("output")[0].value[:-1], "isSecret": True}]:
            changed = copy.deepcopy(records)
            register = next(r for r in changed if r["name"] == "Register 0")
            register["variables"]["OutValue"] = variable
            with self.assertRaises(RuntimeError):
                check_job("output", job, changed, logs, "source", "1")
        for remove in ("Consume 0 OUT", "Unmapped 0", "Register 0"):
            with self.assertRaises(RuntimeError):
                check_job("output", job, [r for r in records if r["name"] != remove], logs, "source", "1")
        changed = copy.deepcopy(records)
        next(r for r in changed if r["name"] == "Register 0")["variables"] = {}
        with self.assertRaises(RuntimeError):
            check_job("output", job, changed, logs, "source", "1")

    def test_metadata_association_cannot_switch_task_or_attempt(self):
        _, records, _ = fixture("output")
        metadata = copy.deepcopy(records)
        for record in records:
            record.pop("variables", None)
        attach_task_metadata(records, metadata)
        self.assertTrue(any(r.get("variables") for r in records))
        for field, value in [("id", "wrong"), ("parentId", "wrong"), ("attempt", 2)]:
            changed = copy.deepcopy(metadata)
            next(r for r in changed if r["name"] == "Register 0")[field] = value
            with self.assertRaises(RuntimeError):
                attach_task_metadata(records, changed)
        with self.assertRaises(RuntimeError):
            attach_task_metadata(records, metadata + [metadata[0]])

    def test_agent_metadata_is_not_an_assignment(self):
        for case in ("ordinary", "output"):
            job, records, logs = fixture(case)
            for record in records:
                if record["name"].startswith("Register "):
                    record.setdefault("variables", {})["agent.version"] = {"value": "5.280.0"}
            check_job(case, job, records, logs, "source", "1")
            for key, value in [("agent.version", {"value": "wrong"}),
                               ("agent.version", {"value": "5.280.0", "isSecret": True}),
                               ("Extra", {"value": "unexpected"})]:
                changed = copy.deepcopy(records)
                next(r for r in changed if r["name"] == "Register 0")["variables"][key] = value
                with self.assertRaises(RuntimeError):
                    check_job(case, job, changed, logs, "source", "1")

    def test_rejection_route_and_masking_are_required(self):
        job, records, logs = fixture("control")
        for message in ("wrong rejection", assignments("control")[0].value):
            changed = copy.deepcopy(records)
            next(r for r in changed if r["name"] == "Expected readonly rejection")["issues"][0]["message"] = message
            with self.assertRaises(RuntimeError):
                check_job("control", job, changed, logs, "source", "1")
        follow = next(r["log"]["id"] for r in records if r["name"] == "Readonly followup")
        with self.assertRaises(RuntimeError):
            check_job("control", job, records, {**logs, follow: logs[follow].replace(b"***", b"**", 1)}, "source", "1")
        reject = next(r["log"]["id"] for r in records if r["name"] == "Expected readonly rejection")
        for leaked in (b"##vso[task.setsecret]unexpected\n", b"##vso[task.setvariable variable=Extra;]x\n"):
            with self.assertRaises(RuntimeError):
                check_job("control", job, records, {**logs, reject: logs[reject] + leaked}, "source", "1")

    def test_wrong_or_truncated_consumer_value_fails_before_logging(self):
        for value in ("wrong", assignments("ordinary")[0].value[:-1]):
            with patch.dict(os.environ, {"SV_MAPPED": value, "CALLERSENTINEL": SENTINEL}, clear=True):
                with self.assertRaises(RuntimeError):
                    consume("ordinary", 0, "OUT")
        with patch.dict(os.environ, {"CREDENTIAL": "unexpected", "CALLERSENTINEL": SENTINEL}, clear=True):
            with self.assertRaises(RuntimeError):
                unmapped("ordinary", 0)
        for index, key in [(0, "PUBLISH0_OUTVALUE"), (1, "PUBLISH1_OUTREADONLY")]:
            with patch.dict(os.environ, {key: "unexpected", "CALLERSENTINEL": SENTINEL}, clear=True):
                with self.assertRaises(RuntimeError):
                    unmapped("output", index)

    def test_control_evidence_cannot_be_skipped_or_masked(self):
        job, records, logs = fixture("control")
        for name in ("Expected readonly rejection", "Readonly followup", "Calibrate OUT",
                     "Calibrate ERR", "Control plain-check", "Control omission-check"):
            with self.subTest(phase=name), self.assertRaises(RuntimeError):
                check_job("control", job, [r for r in records if r["name"] != name], logs, "source", "1")
        changed = copy.deepcopy(records)
        next(r for r in changed if r["name"] == "Expected readonly rejection")["issues"] = []
        with self.assertRaises(RuntimeError):
            check_job("control", job, changed, logs, "source", "1")
        changed = copy.deepcopy(records)
        next(r for r in changed if r["name"] == "Expected readonly rejection")["issues"][0]["message"] = assignments("control")[0].value
        with self.assertRaises(RuntimeError):
            check_job("control", job, changed, logs, "source", "1")
        for name, plaintext in (("Control plain-check", CONTROL_PLAIN),
                                ("Control omission-check", CONTROL_OMITTED)):
            log_id = next(r["log"]["id"] for r in records if r["name"] == name)
            with self.assertRaises(RuntimeError):
                check_job("control", job, records,
                          {**logs, log_id: logs[log_id].replace(plaintext.encode(), b"***")}, "source", "1")
        log_id = next(r["log"]["id"] for r in records if r["name"] == "Expected readonly rejection")
        with self.assertRaises(RuntimeError):
            check_job("control", job, records, {**logs, log_id: b"unrelated failure\n"}, "source", "1")
        job, records, logs = fixture("ordinary")
        next(r for r in records if r["name"] == "Register 0")["variables"] = {"Credential": {"isSecret": True}}
        with self.assertRaises(RuntimeError):
            check_job("ordinary", job, records, logs, "source", "1")


if __name__ == "__main__":
    unittest.main()
