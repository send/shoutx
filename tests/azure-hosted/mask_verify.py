"""Read-only completed-log admission. Never persist or print raw responses."""
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

from mask_cases import blocks, cases, escaped

LIMIT = 32 * 1024 * 1024
TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+Z ")


def require(condition, label):
    if not condition:
        raise RuntimeError(label)


def log_lines(raw):
    text = raw.decode("utf-8", errors="strict")
    return [TIMESTAMP.sub("", line.removesuffix("\r")) for line in text.split("\n")]


def exact_block(lines, tag, expected):
    start, end = tag + "_BEGIN", tag + "_END"
    require(lines.count(start) == 1 and lines.count(end) == 1, "missing/duplicate block")
    begin, finish = lines.index(start), lines.index(end)
    require(finish > begin and lines[begin + 1:finish] == expected, "payload mismatch")


def check_job(case, job, records, logs, source, run):
    require(job["state"] == "completed" and job["result"] == "succeeded", "job not successful")
    owned = [r for r in records if r.get("parentId") == job["id"]]
    require(owned, "missing tasks")
    for record in [job, *owned]:
        require(not record.get("issues") and not record.get("errorCount", 0)
                and not record.get("warningCount", 0), "unexpected issue")
        require(record.get("state") == "completed", "incomplete task")
        require(record.get("attempt", 1) == job.get("attempt", 1), "wrong task attempt")
        if record.get("type") == "Task" and record.get("result") != "skipped":
            require(record.get("log"), "missing task log")
    by_name = {}
    all_raw = []
    for record in [job, *owned]:
        reference = record.get("log")
        if reference:
            raw = logs[reference["id"]]
            all_raw.append(raw)
            by_name[record["name"]] = log_lines(raw)
    require(sum(map(len, all_raw)) <= LIMIT, "job logs too large")
    for name in ("Prepare mask fixture", "Calibrate stderr fixture", "Register masks",
                 "Emit masked stdout", "Emit masked stderr"):
        require(name in by_name, "missing phase log")
    prepare, register = by_name["Prepare mask fixture"], by_name["Register masks"]
    calibration = {"OUT": prepare, "ERR": by_name["Calibrate stderr fixture"]}
    emissions = {"OUT": by_name["Emit masked stdout"], "ERR": by_name["Emit masked stderr"]}
    emit = emissions["OUT"] + emissions["ERR"]
    require(not any(line.startswith("##[debug]") for line in register + emit), "debug enabled")
    identities = [json.loads(line[len("SX_IDENTITY:"):]) for line in prepare
                  if line.startswith("SX_IDENTITY:")]
    require(len(identities) == 1, "identity missing")
    identity = identities[0]
    require(identity["source"] == source and identity["run"] == str(run)
            and identity["job"].lower() == job["id"].lower()
            and identity["attempt"] == str(job.get("attempt", 1))
            and identity["case"] == case.name, "identity mismatch")
    require(all(identity.get(key) for key in ("agent", "image", "imageVersion", "digest")),
            "missing runtime identity")
    require(re.fullmatch(r"[0-9a-f]{64}", identity["digest"]), "invalid binary digest")
    require(prepare.count("SX_PREPARED") == 1 and register.count("SX_REGISTERED") == 1,
            "phase incomplete")
    for stream in ("OUT", "ERR"):
        require(emissions[stream].count("SX_EMISSION_COMPLETE") == 1
                and emissions[stream].count("SX_UNRELATED_VISIBLE") == 1, "emission incomplete")
        require(calibration[stream].count("SX_CALIBRATED") == 1, "calibration incomplete")
    for stream, tag, expected in blocks(case, True):
        exact_block(emissions[stream], tag, expected)
    if case.each_line:
        for stream in ("OUT", "ERR"):
            exact_block(calibration[stream], "SX_FRAMING_" + stream, ["AA", "", "BB", "", "CC", ""])
    if case.name == "lines_cap":
        require(prepare.count("SX_REJECTIONS_OK") == 1, "missing rejection checks")
    if case.name == "lines_omission":
        for name in ("lines_pem", "lines_mixed", "lines_short", "lines_cap"):
            for stream, tag, expected in blocks(cases()[name], False):
                exact_block(calibration[stream], "CAL_" + name.upper() + "_" + tag, expected)
    joined = b"\n".join(all_raw).decode("utf-8")
    registration = "\n".join(register)
    for value in set(case.registered):
        require("##vso[task.setsecret]" + escaped(value) not in registration,
                "registration wire visible")
        # Calibration plaintext is authorized only in prepare's exact blocks.
        scan = "\n".join(register + emit) if case.control else joined
        if len(value) >= 12 and not value.isspace():
            require(value not in scan and escaped(value) not in scan, "registered value visible")
    return {**identity, "control": case.control, "blocks": len(blocks(case, True)),
            "logDigest": hashlib.sha256(b"\n".join(all_raw)).hexdigest()}


def fetch(path, token, base, limit):
    # Construct URLs locally, never follow an API-supplied log URL with a token.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(base + path, headers={
        "Authorization": "Bearer " + token,
        "Accept": "text/plain" if path.startswith("/logs/") else "application/json",
    })
    for attempt in range(6):
        try:
            with opener.open(request, timeout=15) as response:
                data = response.read(limit + 1)
        except Exception:
            if attempt == 5:
                raise RuntimeError("read API failed") from None
            time.sleep(2)
            continue
        require(len(data) <= limit, "response too large")
        return data


def verify():
    collection = os.environ["SYSTEM_COLLECTIONURI"]
    require(collection.startswith("https://dev.azure.com/"), "unexpected API origin")
    project = urllib.parse.quote(os.environ["SYSTEM_TEAMPROJECTID"], safe="")
    run = os.environ["BUILD_BUILDID"]
    source = os.environ["BUILD_SOURCEVERSION"]
    require(run.isdigit(), "invalid run")
    base = collection.rstrip("/") + "/" + project + "/_apis/build/builds/" + run
    token = os.environ["SYSTEM_ACCESSTOKEN"]
    build = json.loads(fetch("?api-version=7.1", token, base, LIMIT))
    require(build["sourceVersion"] == source and str(build["id"]) == run, "wrong source/run")
    records = json.loads(fetch("/timeline?api-version=7.1", token, base, LIMIT))["records"]
    inventory = json.loads(fetch("/logs?api-version=7.1", token, base, LIMIT))["value"]
    log_counts = {entry["id"]: entry["lineCount"] for entry in inventory}
    require(len(log_counts) == len(inventory), "duplicate log inventory")
    results = []
    matrix = cases()
    for platform in ("linux", "windows"):
        digest = None
        for name, case in matrix.items():
            candidates = [r for r in records if r.get("type") == "Job"
                          and r.get("name") == platform + "_" + name]
            require(len(candidates) == 1, "missing/duplicate job")
            job = candidates[0]
            logs, total = {}, 0
            for record in records:
                if record["id"] != job["id"] and record.get("parentId") != job["id"]:
                    continue
                ref = record.get("log")
                if ref and ref["id"] not in logs:
                    data = fetch("/logs/" + str(int(ref["id"])) + "?api-version=7.1",
                                 token, base, LIMIT - total)
                    require(ref["id"] in log_counts, "log absent from inventory")
                    require(data.endswith(b"\n") and data.count(b"\n") == log_counts[ref["id"]],
                            "incomplete log response")
                    total += len(data)
                    logs[ref["id"]] = data
            result = check_job(case, job, records, logs, source, run)
            if digest is None:
                digest = result["digest"]
            require(digest == result["digest"], "binary changed between jobs")
            results.append(result)
    print(json.dumps({"maskHosted": "passed", "source": source, "run": run,
                      "jobs": results}, sort_keys=True))


if __name__ == "__main__":
    try:
        verify()
    except Exception as error:
        # All validation labels are fixed and contain no log values.
        label = str(error) if type(error) is RuntimeError else "unexpected verifier failure"
        sys.exit("Mask hosted verification failed: " + label)
