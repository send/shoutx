"""Synthetic child only; no parent observation and no environment-value output."""
import json
import os
import runpy
import sys


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("absent", "empty", "null", "text"):
        return 2
    mode = sys.argv[1]
    observer = runpy.run_path("hosted_worker.py")
    keys = observer["CONFIGURATION_KEYS"]
    expected = None if mode == "absent" else "synthetic-overlay" if mode == "text" else ""
    result = {
        "case": mode,
        "presence": observer["child_configuration_presence"](os.environ),
        "valuesMatch": all(os.environ.get(key) == expected for key in keys),
        "inheritedControlMatches": os.environ.get("SHOUTX_TRANSPORT_INHERITANCE_CONTROL") == "synthetic-inherited",
    }
    print(json.dumps(result, separators=(",", ":")))
    return 0 if result["valuesMatch"] and result["inheritedControlMatches"] else 1


if __name__ == "__main__":
    sys.exit(main())
