"""Completed-run check, executed outside the four producer jobs. No UI claim."""
import hashlib
import json
import os
import re
import sys
import urllib.parse

from formatter_cases import expected_blocks
from mask_verify import LIMIT, exact_block, fetch, log_lines, require


def check_job(host, mode, job, records, logs, source, run):
    owned = [r for r in records if r.get("parentId") == job["id"]]
    require(owned, "missing tasks")
    for record in [job, *owned]:
        require(record.get("state") == "completed", "incomplete job/task")
        require(record.get("result") in ("succeeded", "skipped"), "failed job/task")
        require(not record.get("issues") and not record.get("errorCount", 0)
                and not record.get("warningCount", 0), "unexpected issue")
        require(record.get("attempt", 1) == job.get("attempt", 1), "attempt mismatch")
        if record.get("type") == "Task" and record.get("result") != "skipped":
            require(record.get("log", {}).get("id") in logs, "missing task log")
    require(job.get("result") == "succeeded", "job not successful")

    def phase(name):
        found = [r for r in owned if r.get("type") == "Task" and r.get("name") == name]
        require(len(found) == 1 and found[0].get("result") == "succeeded", "missing phase")
        return found[0], log_lines(logs[found[0]["log"]["id"]])

    producer, lines = phase("Emit formatter corpus")
    _, sentinel = phase("Verify formatter sentinel")
    require(sentinel.count("SX_SENTINEL_UNCHANGED") == 1, "sentinel changed/missing")
    identities = [json.loads(line.removeprefix("SX_FORMATTER_IDENTITY:")) for line in lines
                  if line.startswith("SX_FORMATTER_IDENTITY:")]
    require(len(identities) == 1, "identity missing/duplicate")
    identity = identities[0]
    require(identity.get("source") == source and identity.get("run") == str(run)
            and identity.get("job", "").lower() == job["id"].lower()
            and identity.get("attempt") == str(job.get("attempt", 1))
            and identity.get("host") == host and identity.get("debug") == mode,
            "identity mismatch")
    require(all(identity.get(key) for key in ("agent", "image", "imageVersion")),
            "missing runtime identity")
    require(re.fullmatch(r"[0-9a-f]{64}", identity.get("digest", "")), "invalid digest")
    for marker in ("SX_REJECTIONS_OK", "SX_AFTER_ALL_GROUPS", "SX_FORMATTER_COMPLETE"):
        require(lines.count(marker) == 1, "missing/duplicate completion marker")
    require(lines.index("SX_NESTED_END") < lines.index("SX_AFTER_ALL_GROUPS")
            < lines.index("SX_FORMATTER_COMPLETE"), "wrong group completion order")
    for tag, expected in expected_blocks(mode == "on").items():
        exact_block(lines, tag, expected)
    return {**identity, "producerTask": producer["id"], "producerLog": producer["log"]["id"],
            "logDigest": hashlib.sha256(logs[producer["log"]["id"]]).hexdigest(),
            "blocks": len(expected_blocks(mode == "on"))}


def verify():
    run, source = os.environ["BUILD_BUILDID"], os.environ["BUILD_SOURCEVERSION"]
    require(run.isascii() and run.isdigit(), "invalid run")
    require(re.fullmatch(r"[0-9a-f]{40}", source), "invalid source")
    project = urllib.parse.quote(os.environ["SYSTEM_TEAMPROJECTID"], safe="")
    base = "https://dev.azure.com/kazjuly7/" + project + "/_apis/build/builds/" + run
    token = os.environ["SYSTEM_ACCESSTOKEN"]
    build = json.loads(fetch("?api-version=7.1", token, base, LIMIT))
    require(build.get("sourceVersion") == source and str(build.get("id")) == run,
            "wrong source/run")
    require(build.get("status") == "completed" and build.get("result") == "succeeded",
            "build not completed successfully")
    records = json.loads(fetch("/timeline?api-version=7.1", token, base, LIMIT))["records"]
    inventory = json.loads(fetch("/logs?api-version=7.1", token, base, LIMIT))["value"]
    counts = {entry["id"]: entry["lineCount"] for entry in inventory}
    require(len(counts) == len(inventory), "duplicate log inventory")
    jobs = [r for r in records if r.get("type") == "Job"]
    require(sorted(j.get("name", "") for j in jobs)
            == ["linux_off", "linux_on", "windows_off", "windows_on"], "wrong job matrix")
    results = []
    for host in ("linux", "windows"):
        digest = None
        for mode in ("off", "on"):
            job = next(j for j in jobs if j["name"] == host + "_" + mode)
            logs, total = {}, 0
            for record in records:
                if record["id"] != job["id"] and record.get("parentId") != job["id"]:
                    continue
                ref = record.get("log")
                if ref and ref["id"] not in logs:
                    data = fetch("/logs/" + str(int(ref["id"])) + "?api-version=7.1",
                                 token, base, LIMIT - total)
                    require(ref["id"] in counts and data.endswith(b"\n")
                            and data.count(b"\n") == counts[ref["id"]], "incomplete log")
                    total += len(data)
                    logs[ref["id"]] = data
            result = check_job(host, mode, job, records, logs, source, run)
            if digest is None:
                digest = result["digest"]
            require(digest == result["digest"], "binary changed between jobs")
            results.append(result)
    print(json.dumps({"formatterLogs": "passed", "ui": "not-verified",
                      "source": source, "run": run, "jobs": results}, sort_keys=True))


if __name__ == "__main__":
    try:
        verify()
    except Exception:
        sys.exit("Azure formatter completed-log verification failed; captured data withheld")
