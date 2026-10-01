#!/usr/bin/env python3
"""Generate a RESEARCH-ONLY V2 data-start candidate; never a CLI acceptance rule.

Supply the three official files named in unicode-pins.json in --source-dir.
No network or runtime Unicode tables are used by this generator.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS = ROOT / "tests/runner-package/unicode-pins.json"
TABLE = ROOT / "tests/runner-package/unicode-candidate.json"
GCB = {"Other", "L", "V", "T", "LV", "LVT", "Regional_Indicator"}


def properties(text):
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        interval, prop = (part.strip() for part in line.split(";"))
        bounds = interval.split("..")
        yield int(bounds[0], 16), int(bounds[-1], 16), prop


def candidates(unicode_data, grapheme, derived):
    selected = set()
    pending = None
    for line in unicode_data.splitlines():
        if not line:
            continue
        fields = line.split(";")
        cp, name, category = int(fields[0], 16), fields[1], fields[2]
        if name.endswith(", First>"):
            if pending is not None:
                raise ValueError("nested Unicode range")
            pending = (cp, category)
            continue
        if name.endswith(", Last>"):
            if pending is None or pending[1] != category or pending[0] > cp:
                raise ValueError("invalid Unicode range")
            start = pending[0]
            pending = None
        else:
            if pending is not None:
                raise ValueError("unterminated Unicode range")
            start = cp
        if category[0] in "LNPS":
            selected.update(range(start, cp + 1))
    if pending is not None:
        raise ValueError("unterminated Unicode range")
    # The UCD declares omitted GCB entries Other. Unassigned characters are
    # nevertheless excluded by the positive category selection above.
    for start, end, prop in properties(grapheme):
        if prop not in GCB:
            selected.difference_update(range(start, end + 1))
    for start, end, prop in properties(derived):
        if prop == "Default_Ignorable_Code_Point":
            selected.difference_update(range(start, end + 1))
    if not selected or any(cp == 0 or 0xd800 <= cp <= 0xdfff or cp > 0x10ffff for cp in selected):
        raise ValueError("invalid candidate set")
    return sorted(selected)


def ranges(points):
    result = []
    for cp in points:
        if result and result[-1][1] + 1 == cp:
            result[-1][1] = cp
        else:
            result.append([cp, cp])
    return result


def generate(directory):
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    sources = {}
    for source in pins["sources"]:
        raw = (directory / source["name"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError("Unicode source digest mismatch")
        sources[source["name"]] = raw.decode("utf-8")
    points = candidates(sources["UnicodeData.txt"], sources["GraphemeBreakProperty.txt"], sources["DerivedCoreProperties.txt"])
    table = {"schemaVersion": 1, "unicodeVersion": pins["unicodeVersion"],
             "researchOnly": True, "count": len(points), "ranges": ranges(points)}
    return (json.dumps(table, separators=(",", ":")) + "\n").encode("ascii")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = generate(args.source_dir)
    if args.check:
        if TABLE.read_bytes() != content:
            raise ValueError("committed Unicode candidate differs from pinned generation")
    else:
        TABLE.write_bytes(content)


if __name__ == "__main__":
    main()
