"""Completed secret-variable admission. API bodies and secrets stay in memory."""
import json
import os
import re
import sys
import urllib.parse

from mask_verify import LIMIT, exact_block, fetch, log_lines, require
from secret_cases import (ALL_JOBS, SAME_JOB, assignments, expected_blocks, escaped,
                          CONTROL_PLAIN, CONTROL_OMITTED, CONTROL_WRONG,
                          CONTROL_REPLACEMENT)


def check_job(case, job, records, logs, source, run):
    control = case == "control"
    require(job.get("state") == "completed" and job.get("result") in
            (("succeeded", "succeededWithIssues") if control else ("succeeded",)),
            "job not successful")
    owned = [record for record in records if record.get("parentId") == job["id"]]
    require(owned, "missing tasks")
    named, raw_parts = {}, []
    for record in [job, *owned]:
        expected_rejection = control and record.get("name") == "Expected readonly rejection"
        require(record.get("state") == "completed", "incomplete record")
        require(record.get("attempt", 1) == job.get("attempt", 1), "wrong task attempt")
        issues = record.get("issues", [])
        if expected_rejection:
            require(issues and record.get("result") in ("succeededWithIssues", "failed", "succeeded"),
                    "missing readonly rejection")
            for issue in issues:
                message = issue.get("message", "")
                for value in (CONTROL_REPLACEMENT, *(a.value for a in assignments(case))):
                    require(value not in message and escaped(value) not in message,
                            "rejected value disclosed")
        else:
            require(not issues, "unexpected issue")
            if not (control and record is job):
                require(not record.get("warningCount", 0) and not record.get("errorCount", 0),
                        "unexpected issue count")
        if record.get("type") == "Task" and record.get("result") != "skipped":
            require(record.get("result") == "succeeded" or expected_rejection, "task failed")
            require(record.get("log"), "missing task log")
        reference = record.get("log")
        if reference:
            require(reference["id"] in logs, "log not retrieved")
            raw = logs[reference["id"]]
            require(record["name"] not in named, "duplicate task name")
            named[record["name"]] = log_lines(raw)
            raw_parts.append(raw)
    require(sum(map(len, raw_parts)) <= LIMIT, "job logs too large")
    require("Prepare secret fixture" in named, "missing prepare")
    prepare = named["Prepare secret fixture"]
    identities = [json.loads(line[len("SV_IDENTITY:"):]) for line in prepare
                  if line.startswith("SV_IDENTITY:")]
    require(len(identities) == 1 and prepare.count("SV_PREPARED") == 1, "incomplete prepare")
    identity = identities[0]
    require(identity.get("source") == source and identity.get("run") == str(run)
            and identity.get("job", "").lower() == job["id"].lower()
            and identity.get("attempt") == str(job.get("attempt", 1))
            and identity.get("case") == case, "identity mismatch")
    require(all(identity.get(key) for key in ("agent", "image", "imageVersion", "digest")),
            "missing runtime identity")
    require(re.fullmatch(r"[0-9a-f]{64}", identity["digest"]), "invalid binary digest")
    require(identity["image"] == ("ubuntu24" if job["name"].startswith("linux_") else "win25"),
            "wrong image generation")
    joined = b"\n".join(raw_parts).decode("utf-8", errors="strict")
    require("##[debug]" not in joined, "debug enabled")
    require("##vso[task.setvariable " not in joined, "registration wire visible")
    for index, assignment in enumerate(assignments(case)):
        if case not in ("dependent", "stage"):
            register = named.get(f"Register {index}", [])
            require(register.count(f"SV_REGISTERED_{index}") == 1, "missing registration")
        unmapped = named.get(f"Unmapped {index}", [])
        require(unmapped.count(f"SV_UNMAPPED_{index}_OK") == 1, "missing unmapped check")
        for stream in ("OUT", "ERR"):
            lines = named.get(f"Consume {index} {stream}", [])
            require(lines.count(f"SV_CONSUMED_{index}_{stream}_OK") == 1, "consumer incomplete")
            for tag, expected in expected_blocks(case, index, stream, True):
                exact_block(lines, tag, expected)
        if len(assignment.value) >= 12 and not assignment.value.isspace():
            require(assignment.value not in joined and escaped(assignment.value) not in joined,
                    "registered value visible")
        if case == "output":
            registrations = [record for record in owned if record.get("name") == f"Register {index}"]
            require(len(registrations) == 1, "missing output source")
            variables = registrations[0].get("variables", {})
            require(set(variables) == {assignment.name}, "wrong output variables")
            variable = variables[assignment.name]
            require(variable.get("isSecret") is True and variable.get("value") == assignment.value,
                    "output metadata mismatch")
    if case in ("size", "control"):
        require(prepare.count("SV_REJECTIONS_OK") == 1, "missing rejection probes")
    if control:
        for stream in ("OUT", "ERR"):
            calibration = named.get("Calibrate " + stream, [])
            require(calibration.count("SV_CALIBRATED_" + stream) == 1, "missing calibration")
            for target in (*SAME_JOB, "output"):
                for index in range(len(assignments(target))):
                    for tag, expected in expected_blocks(target, index, stream, False):
                        exact_block(calibration, "CAL_" + tag, expected)
        exact_block(named.get("Control plain-check", []), "SV_PLAIN", [CONTROL_PLAIN])
        require(named.get("Control plain", []).count("SV_PLAIN_REGISTERED") == 1,
                "missing nonsecret control")
        require(named.get("Control wrong", []).count("SV_WRONG_REGISTERED") == 1,
                "missing wrong-registration control")
        for tag in ("SV_OMISSION", "SV_WRONG"):
            exact_block(named.get("Control omission-check", []), tag, [CONTROL_OMITTED])
        require(named.get("Readonly followup", []).count("SV_READONLY_UNCHANGED") == 1,
                "readonly changed or unchecked")
        require(any(r.get("name") == "Expected readonly rejection" and r.get("issues") for r in owned),
                "missing expected rejection issue")
        require(CONTROL_REPLACEMENT not in joined and CONTROL_WRONG not in joined,
                "control registration disclosed")
    # Only public identities/results leave the verifier, not values or their hashes.
    return {**identity, "assignments": len(assignments(case)), "control": control}


def check_inventory(records):
    names = [r.get("name") for r in records if r.get("type") == "Job"]
    expected = {platform + "_" + case for platform in ("linux", "windows") for case in ALL_JOBS}
    expected.add("verify_secrets")
    require(len(names) == 21 and set(names) == expected, "unexpected job inventory")


def verify():
    collection = os.environ["SYSTEM_COLLECTIONURI"]
    require(collection.startswith("https://dev.azure.com/"), "unexpected API origin")
    project = urllib.parse.quote(os.environ["SYSTEM_TEAMPROJECTID"], safe="")
    run, source = os.environ["BUILD_BUILDID"], os.environ["BUILD_SOURCEVERSION"]
    require(run.isdigit(), "invalid run")
    base = collection.rstrip("/") + "/" + project + "/_apis/build/builds/" + run
    token = os.environ["SYSTEM_ACCESSTOKEN"]
    build = json.loads(fetch("?api-version=7.1", token, base, LIMIT))
    require(build["sourceVersion"] == source and str(build["id"]) == run, "wrong source/run")
    records = json.loads(fetch("/timeline?api-version=7.1", token, base, LIMIT))["records"]
    check_inventory(records)
    inventory = json.loads(fetch("/logs?api-version=7.1", token, base, LIMIT))["value"]
    counts = {entry["id"]: entry["lineCount"] for entry in inventory}
    require(len(counts) == len(inventory), "duplicate log inventory")
    results = []
    for platform in ("linux", "windows"):
        digest = None
        for case in ALL_JOBS:
            jobs = [r for r in records if r.get("type") == "Job" and r.get("name") == platform + "_" + case]
            require(len(jobs) == 1, "missing/duplicate job")
            job = jobs[0]
            logs, total = {}, 0
            for record in records:
                if record["id"] != job["id"] and record.get("parentId") != job["id"]:
                    continue
                ref = record.get("log")
                if ref and ref["id"] not in logs:
                    data = fetch("/logs/" + str(int(ref["id"])) + "?api-version=7.1",
                                 token, base, LIMIT - total)
                    require(ref["id"] in counts, "log absent from inventory")
                    require(data.endswith(b"\n") and data.count(b"\n") == counts[ref["id"]],
                            "incomplete log response")
                    total += len(data)
                    logs[ref["id"]] = data
            result = check_job(case, job, records, logs, source, run)
            if digest is None:
                digest = result["digest"]
            require(digest == result["digest"], "binary changed between jobs")
            results.append(result)
    print(json.dumps({"secretVariableHosted": "passed", "source": source,
                      "run": run, "jobs": results}, sort_keys=True))


if __name__ == "__main__":
    try:
        verify()
    except Exception:
        sys.exit("Secret-variable admission failed; logs and values withheld")
