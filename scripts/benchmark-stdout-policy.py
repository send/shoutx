"""Synthetic CLI benchmark; no input values are included in the report.

Run before/after binaries together on the same host for the acceptance comparison.
Baseline-only mode records workload execution and checks the harness.
"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time

WORKLOADS = [
    ("short", "mask", b"A short value"),
    ("unicode-tail", "warning", "A Ελληνικά العربية हिन्दी 日本語 😀".encode()),
    ("annotation-limit", "warning", b"A" * 4096),
    ("annotation-supplementary", "warning", ("AA" + "😀" * 2047).encode()),
    ("mask-limit", "mask", b"A" * 1048576),
    ("mask-supplementary", "mask", ("AAAA" + "😀" * 262143).encode()),
    ("mask-escaped", "mask", b"%\r\n" * 349525 + b"x"),
]

def execute(binary, command, value):
    start = time.perf_counter_ns()
    result = subprocess.run([str(binary), "github-actions:" + command], input=value,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    elapsed = (time.perf_counter_ns() - start) / 1000000
    if result.returncode != 0 or result.stderr:
        raise ValueError("benchmark workload was not accepted cleanly")
    return elapsed

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binaries = [args.baseline.resolve()] + ([args.candidate.resolve()] if args.candidate else [])
    report = {"samples": 31, "warmups": 3, "units": "milliseconds",
              "scope": "CLI end-to-end, includes startup; no isolated lookup timing",
              "threshold": "candidate median <= max(baseline median * 1.25, baseline median + 0.5ms)",
              "binarySha256": [hashlib.sha256(p.read_bytes()).hexdigest() for p in binaries], "workloads": []}
    passed = True
    for label, command, value in WORKLOADS:
        for binary in binaries:
            for _ in range(3):
                execute(binary, command, value)
        samples = [[] for _ in binaries]
        for i in range(31):
            order = list(range(len(binaries)))
            if i % 2:
                order.reverse()
            for j in order:
                samples[j].append(execute(binaries[j], command, value))
        medians = [statistics.median(s) for s in samples]
        limit = max(medians[0] * 1.25, medians[0] + 0.5)
        accepted = len(medians) == 1 or medians[1] <= limit
        passed &= accepted
        report["workloads"].append({"name": label, "inputBytes": len(value), "median": medians,
                                     "limit": limit, "comparisonPassed": accepted if len(medians) > 1 else None})
    report["comparisonPassed"] = passed if args.candidate else None
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"baselineOnly": args.candidate is None, "comparisonPassed": report["comparisonPassed"]}))
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
