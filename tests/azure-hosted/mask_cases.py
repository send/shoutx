"""Finite synthetic corpus shared by producers and completed-log expectations.

These strings are public test data, never credentials. Expected registrations
are explicit; log verification does not infer them from shoutx output.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re


@dataclass(frozen=True)
class Case:
    name: str
    inputs: tuple[str, ...]
    registered: tuple[str, ...]
    values: tuple[str, ...]
    layout: str | None = None
    each_line: bool = False
    control: bool = False


def entries(value):
    return tuple(part for part in re.split(r"\r\n|\r|\n", value) if part)


def cap_lines():
    # 1,024 distinct entries plus 1,023 LF separators total exactly 1 MiB.
    result = []
    for index in range(1024):
        length = 1024 if index == 1023 else 1023
        digest = hashlib.sha256(f"synthetic-line-{index}".encode()).hexdigest()
        result.append((digest * 17)[:length])
    assert len("\n".join(result).encode()) == 1_048_576
    return tuple(result)


def cases():
    original = "synthetic-original-fd947be08c"
    derived = "synthetic-independent-derived-938bae12"
    near = ("synthetic-limit-" + "0123456789abcdef" * 65536)[:1_048_576]
    result = []
    for name, value in [
        ("ascii", "q"), ("unicode", "🦊"),
        ("escapes", "synthetic-escape-%0A;%AZP25]literal-94bf"),
        ("spaces", " synthetic-spaces-c20a "),
        ("json", '{"synthetic":"opaque-93fb","count":7}'),
        ("whitespace", " "), ("nearcap", near),
    ]:
        result.append(Case(name, (value,), (value,), (value,)))
    result.insert(5, Case("derived", (original, derived), (original, derived),
                          (original, derived)))
    result.extend([
        Case("missing", (), (), tuple(v for case in result for v in case.values), control=True),
        Case("wrong", ("synthetic-other-70af",), ("synthetic-other-70af",),
             (original,), control=True),
        Case("original", (original,), (original,), (original, derived), control=True),
    ])
    layouts = [
        ("lines_pem", "SHOUTX SYNTHETIC BLOCK\nsynthetic-body-c7a41\n"
         "synthetic-body-c7a41\nq\nSHOUTX SYNTHETIC END\n"),
        ("lines_mixed", "\r\nsynthetic-αไทย日本語-c8e9\r\n\r\n"
         "synthetic-%0A;%AZP25]-c9f0\rsynthetic-tail-a7b9\n\n"),
        ("lines_short", "🦊\n\t\n🦉\r\n"),
        ("lines_cap", "\n".join(cap_lines())),
    ]
    for name, layout in layouts:
        selected = entries(layout)
        result.append(Case(name, (layout,), selected, selected, layout, True))
    keep, omit, last = "synthetic-keep-393a", "synthetic-omit-942b", "synthetic-last-702c"
    result.append(Case("lines_omission", (keep + "\n" + last,), (keep, last),
                       (keep, omit, last), keep + "\n" + omit + "\n" + last,
                       True, True))
    assert len(result) == 16
    return {case.name: case for case in result}


def escaped(value):
    # Independent protocol representation for disclosure searches only.
    return (value.replace("%", "%AZP25").replace("\r", "%0D")
            .replace("\n", "%0A").replace(";", "%3B").replace("]", "%5D"))


def redact(value, registered):
    # Merge literal intervals like a masker, without encoding-provider inference.
    spans = []
    for secret in set(registered):
        start = value.find(secret)
        while start >= 0:
            spans.append((start, start + len(secret)))
            start = value.find(secret, start + 1)
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    out, cursor = [], 0
    for start, end in merged:
        out.extend([value[cursor:start], "***"])
        cursor = end
    return "".join(out) + value[cursor:]


def blocks(case, masked):
    """Exact payload lines; caller strips timestamps, not whitespace."""
    registered = case.registered if masked else ()
    result = []
    for index, value in enumerate(case.values):
        for stream in ("OUT", "ERR"):
            for form in ("WHOLE", "WRAPPED"):
                tag = f"SX_{stream}_{form}_{index}"
                payload = value if form == "WHOLE" else "PREFIX" + value + "SUFFIX"
                result.append((stream, tag, [redact(payload, registered)]))
    if case.layout is not None:
        for stream in ("OUT", "ERR"):
            # CRLF / CR / LF transport projection is calibrated before masks.
            lines = re.split(r"\r\n|\r|\n", case.layout)
            result.append((stream, f"SX_{stream}_LAYOUT",
                           [redact(line, registered) for line in lines]))
    return result
