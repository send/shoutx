"""Finite public synthetic credentials, never real secrets or live commands."""
from dataclasses import dataclass

from mask_cases import escaped


@dataclass(frozen=True)
class Assignment:
    name: str
    value: str
    output: bool = False
    read_only: bool = False


SAME_JOB = ("ordinary", "unicode", "ascii", "supplementary", "whitespace", "size")
ALL_JOBS = (*SAME_JOB, "output", "dependent", "stage", "control")
SENTINEL = "caller-sentinel-unchanged"
CONTROL_PLAIN = "synthetic-visible-plain-cf28"
CONTROL_OMITTED = "synthetic-omitted-45ae"
CONTROL_WRONG = "synthetic-wrong-registration-97fe"
CONTROL_ORIGINAL = "synthetic-readonly-original-60bf"
CONTROL_REPLACEMENT = "synthetic-readonly-replacement-4c81"


def assignments(case):
    values = {
        "ordinary": (Assignment("Credential", "synthetic-runtime-credential-984fe3", read_only=True),),
        "unicode": (Assignment("Credential", "synthetic-αไทย日本語😀-%0A;%AZP25]-67c8"),),
        "ascii": (Assignment("Credential", "q"),),
        "supplementary": (Assignment("Credential", "🦊"),),
        "whitespace": (Assignment("Credential", " \t "),),
        "size": (Assignment("CapAscii", ("8d3e70a15b924fc6" * 1024)),
                 Assignment("CapUnicode", "🦉" * 4096)),
        "output": (Assignment("OutValue", "synthetic-output-α😀-%0A;]-3f9a", output=True),
                   Assignment("OutReadOnly", "synthetic-output-ro-ไทย-%AZP25]-c4e8",
                              output=True, read_only=True)),
        "control": (Assignment("Locked", CONTROL_ORIGINAL, read_only=True),),
    }
    return values["output" if case in ("dependent", "stage") else case]


def block_tag(case, index, stream, wrapped):
    return f"SV_{case.upper()}_{index}_{stream}_{'WRAPPED' if wrapped else 'WHOLE'}"


def expected_blocks(case, index, stream, masked):
    value = "***" if masked else assignments(case)[index].value
    return [(block_tag(case, index, stream, False), [value]),
            (block_tag(case, index, stream, True), ["PREFIX" + value + "SUFFIX"])]
