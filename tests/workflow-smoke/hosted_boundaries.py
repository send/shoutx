"""Bounded live-Runner experiment. All values are synthetic, never credentials."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

STARTS = ("A", ":", "%", " ", "-", "'", "#", "0")
FIELDS = ("annotation_level", "title", "message", "path", "start_line",
          "end_line", "start_column", "end_column")
BEGIN = "SHOUTX_HOSTED_BOUNDARIES_BEGIN"
END = "SHOUTX_HOSTED_BOUNDARIES_END"
FINISH = "SHOUTX_HOSTED_TEST_SEQUENCE_COMPLETE"
IDENTITY = "SHOUTX_HOSTED_IDENTITY="


def annotations():
    result = []
    for command in ("notice", "warning", "error"):
        for index, start in enumerate((*STARTS, "\r", "\n")):
            tag = f"shoutx-boundary-{command}-{index:02}"
            result.append({
                "annotation_level": "failure" if command == "error" else command,
                "title": f"{tag} :: %,=ASCII",
                "message": (start + "\u0301\u200d\U0001f44d\U0001f3fb日本語 %0A " + tag
                            + "\n##[warning]" + tag + " ::error::data"),
                "path": "src/hosted-boundary,percent%25-ASCII.rs",
                "start_line": index + 1, "end_line": index + 1,
                "start_column": 1, "end_column": 2,
            })
    return result


def mask_values(run_id, attempt, runner_os):
    # Reconstructible canaries let the verifier detect raw/encoded leakage
    # anywhere in the completed job log, including failed command registration.
    for index, start in enumerate(STARTS):
        digest = hashlib.sha256(f"{run_id}:{attempt}:{runner_os}:{index}".encode()).hexdigest()
        marker = "shoutx-boundary-mask-" + digest
        yield start + "\u0301\U0001f44d\U0001f3fb##[warning]" + marker + "::error::%0A", marker


def write_line(value):
    sys.stdout.buffer.write(value.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def emit():
    binary = os.environ["UNSTABLE_BINARY"]
    identity = {name: os.environ.get(name) for name in
                ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "RUNNER_OS",
                 "RUNNER_ARCH", "ImageOS", "ImageVersion", "SHOUTX_SOURCE_HEAD")}
    if not all(identity.values()):
        raise ValueError("hosted identity is incomplete")
    write_line(IDENTITY + json.dumps(identity, sort_keys=True))
    write_line(BEGIN)
    masks = list(mask_values(identity["GITHUB_RUN_ID"], identity["GITHUB_RUN_ATTEMPT"],
                             identity["RUNNER_OS"]))
    # Inherit stdout: native shoutx bytes go directly to the live Runner.
    # Never capture, decode and re-emit a command in this hosted experiment.
    for value, _ in masks:
        invoke(binary, "mask", [], value)
    # Legacy commands are recognized even inside ordinary log lines. Suspend
    # parsing ONLY when printing masked samples, after all registrations; the
    # masker still runs. Resume before annotations, which prove processing resumed.
    token = secrets.token_hex(32)
    write_line("::stop-commands::" + token)
    for index, (value, _) in enumerate(masks):
        write_line(f"SHOUTX_BOUNDARY_MASK_{index:02}_BEGIN{value}_END")
    write_line("::" + token + "::")
    for item in annotations():
        command = "error" if item["annotation_level"] == "failure" else item["annotation_level"]
        invoke(binary, command,
               ["--title", item["title"], "--file", str(Path(os.environ["GITHUB_WORKSPACE"]) / item["path"]),
                "--line", str(item["start_line"]), "--end-line", str(item["end_line"]),
                "--column", "1", "--end-column", "2"], item["message"])
    write_line(END)


def invoke(binary, command, options, value):
    result = subprocess.run([binary, "github-actions:" + command, *options],
                            input=value.encode("utf-8"), stderr=subprocess.PIPE)
    if result.returncode != 0 or result.stderr:
        # Do not print captured diagnostics or data on a failure.
        raise ValueError("hosted producer failed")


def log_lines(raw):
    # Do not use splitlines(): Unicode line separators are value data.
    # GitHub's downloaded job log may have one UTF-8 BOM at the file start.
    raw = raw.removeprefix("\ufeff")
    # This corpus has neither CR-final data lines nor timestamp-shaped starts
    # on continuation lines. Extend this model before adding those cases.
    return [re.sub(r"^\d{4}-\d{2}-\d{2}T\S+Z ", "", line.removesuffix("\r"))
            for line in raw.split("\n")]


def expected_block():
    lines = ["::stop-commands::***"]
    lines += [f"SHOUTX_BOUNDARY_MASK_{i:02}_BEGIN***_END" for i in range(len(STARTS))]
    lines += ["::***::"]
    for item in annotations():
        severity = "error" if item["annotation_level"] == "failure" else item["annotation_level"]
        # ExecutionContext adds the severity tag once, before the whole message.
        # A bare CR is preserved, not a line boundary in its LF paging logger.
        lines.extend(("##[" + severity + "]" + item["message"]).split("\n"))
    return lines


def verify(raw, actual, runner_os, run_id, attempt, sha, head):
    lines = log_lines(raw)
    if lines.count(BEGIN) != 1 or lines.count(END) != 1:
        raise ValueError("missing or duplicate experiment boundaries")
    if lines.count(FINISH) != 1 or lines.index(FINISH) <= lines.index(END):
        raise ValueError("missing or misplaced final test sentinel")
    if lines[lines.index(BEGIN) + 1:lines.index(END)] != expected_block():
        raise ValueError("hosted log content/order/count mismatch")
    for _, marker in mask_values(run_id, attempt, runner_os):
        if marker in raw:
            raise ValueError("synthetic mask marker leaked")
    expected = annotations()
    # Scope API matching by either message OR title; lost metadata and fallback
    # warnings still get counted. The block comparison covers log-visible
    # effects in this corpus, not arbitrary silent commands or other steps.
    observed = [item for item in actual if "shoutx-boundary-" in (item.get("title") or "")
                or "shoutx-boundary-" in (item.get("message") or "")]
    project = lambda item: tuple(item.get(field) for field in FIELDS)
    if Counter(map(project, expected)) != Counter(map(project, observed)):
        raise ValueError("hosted annotation content/count mismatch")
    identities = [json.loads(line[len(IDENTITY):]) for line in lines if line.startswith(IDENTITY)]
    if len(identities) != 1:
        raise ValueError("missing or duplicate hosted identity")
    identity = identities[0]
    for name, value in (("GITHUB_RUN_ID", run_id), ("GITHUB_RUN_ATTEMPT", attempt),
                        ("GITHUB_SHA", sha), ("RUNNER_OS", runner_os), ("SHOUTX_SOURCE_HEAD", head)):
        if identity.get(name) != value:
            raise ValueError("hosted identity mismatch")
    if not all(isinstance(identity.get(name), str) and identity[name]
               for name in ("RUNNER_ARCH", "ImageOS", "ImageVersion")):
        raise ValueError("missing hosted image/architecture")
    versions = [match.group(1) for line in lines
                if (match := re.fullmatch(r"Current runner version: '([0-9]+\.[0-9]+\.[0-9]+)'", line))]
    if len(versions) != 1:
        raise ValueError("missing or ambiguous Runner version")
    pins = json.loads((Path(__file__).resolve().parents[1] / "runner-package/pins.json").read_text())
    return {"status": "passed", "identity": identity, "runnerVersion": versions[0],
            "pinnedRunnerVersion": pins["runnerVersion"],
            "runnerMatchesPin": versions[0] == pins["runnerVersion"],
            "workerCulture": None, "workerGlobalizationBackend": None,
            "maskCases": len(STARTS), "annotationCases": len(expected),
            "logSha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()}


def summarize(directory, context):
    """Summarize fresh verified reports, never raw logs/API values."""
    pinned = json.loads((Path(__file__).resolve().parents[1] / "runner-package/pins.json").read_text())["runnerVersion"]
    rows = ["## Hosted Runner compatibility observations", "",
            "| OS | Observed Runner | Pinned Runner | Comparison | Image / version |",
            "| --- | --- | --- | --- | --- |"]
    complete = True
    mismatch = False
    for label, runner_os in (("ubuntu-latest", "Linux"), ("macos-latest", "macOS"),
                             ("windows-latest", "Windows")):
        try:
            report = json.loads((directory / (label + ".json")).read_text(encoding="utf-8"))
            identity = report["identity"]
            if (report["status"] != "passed" or report["maskCases"] != len(STARTS)
                    or report["annotationCases"] != len(annotations())
                    or report["pinnedRunnerVersion"] != pinned
                    or identity["RUNNER_OS"] != runner_os
                    or report["verifierAttempt"] != context["GITHUB_RUN_ATTEMPT"]
                    or any(identity[key] != context[key] for key in
                           ("GITHUB_RUN_ID", "GITHUB_SHA", "SHOUTX_SOURCE_HEAD"))):
                raise ValueError("incomplete evidence")
            version = report["runnerVersion"]
            matches = version == pinned
            if report["runnerMatchesPin"] is not matches:
                raise ValueError("inconsistent comparison")
            image, image_version = identity["ImageOS"], identity["ImageVersion"]
            # Narrow display grammar prevents Markdown/HTML/control injection.
            for value in (version, pinned, image, image_version):
                if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value):
                    raise ValueError("invalid display field")
            comparison = "MATCH" if matches else "DIFFERS - review required"
            mismatch |= not matches
            rows.append(f"| {runner_os} | {version} | {pinned} | {comparison} | {image} / {image_version} |")
        except (ValueError, KeyError, OSError, TypeError, AttributeError):
            complete = False
            rows.append(f"| {runner_os} | unavailable | unavailable | INCOMPLETE | unavailable |")
    rows += ["", "These are hosted behavioral observations, not a support guarantee.",
             "Worker culture/backend remain unknown; version equality is not package identity."]
    if mismatch:
        rows += ["", "A hosted Runner differs from the pin. Review its source/runtime and results;",
                 "update pins only in a separately reviewed PR. No pin was changed automatically."]
    if not complete:
        rows += ["", "Evidence is incomplete or stale. Do not treat this run as passing evidence."]
    rows += ["", "Consult the CI result and the separate completed-log verifier as well.", ""]
    return "\n".join(rows), complete


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("emit", "verify", "finish", "summary"))
    parser.add_argument("--log", type=Path)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--os", choices=("Linux", "macOS", "Windows"))
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--job-id", type=int)
    parser.add_argument("--source-attempt")
    args = parser.parse_args()
    try:
        if args.mode == "emit":
            emit()
        elif args.mode == "finish":
            write_line(FINISH)
        elif args.mode == "summary":
            summary, complete = summarize(args.evidence, os.environ)
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as output:
                output.write(summary)
            return 0 if complete else 1
        else:
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text('{"status": "failed"}\n', encoding="utf-8")
            # Preserve CR and UTF-8 strictly; no universal-newline conversion.
            raw = args.log.read_bytes().decode("utf-8")
            report = verify(raw, json.loads(args.annotations.read_text(encoding="utf-8")),
                            args.os, os.environ["GITHUB_RUN_ID"], args.source_attempt,
                            os.environ["GITHUB_SHA"], os.environ["SHOUTX_SOURCE_HEAD"])
            report["harnessSha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            report["jobId"] = args.job_id
            report["verifierAttempt"] = os.environ["GITHUB_RUN_ATTEMPT"]
            report["annotationsSha256"] = hashlib.sha256(args.annotations.read_bytes()).hexdigest()
            args.evidence.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except (ValueError, KeyError, OSError, TypeError, AttributeError):
        # No tracebacks, raw API/log data or candidate values in workflow output.
        print("Hosted boundary experiment failed; inspect the completed source job.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
