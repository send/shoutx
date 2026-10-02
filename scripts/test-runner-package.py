#!/usr/bin/env python3
"""Package-backed parser evidence; Python 3.10+, .NET SDK, and Cargo required.

No runner registration. Downloads are anonymous and digest-checked before use.
Only root bin/ regular files are extracted into a fresh private staging tree.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import sys
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PINS = ROOT / "tests/runner-package/pins.json"


def digest(path):
    with path.open("rb") as stream:
        value = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def verify(path, expected, size=None):
    if (size is not None and path.stat().st_size != size) or digest(path) != expected:
        raise ValueError("pinned download identity mismatch")


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise ValueError("non-HTTPS redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, destination, limit):
    if not url.startswith("https://"):
        raise ValueError("non-HTTPS URL")
    opener = urllib.request.build_opener(HTTPSRedirect())
    with opener.open(url, timeout=60) as response, destination.open("xb") as output:
        total = 0
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > limit:
                raise ValueError("download exceeds limit")
            output.write(chunk)


def bin_name(name):
    # Ignore everything except immediate bin children; never interpret archive paths.
    parts = PurePosixPath(name).parts
    if len(parts) != 2 or parts[0] != "bin":
        return None
    leaf = parts[1]
    if leaf in (".", "..") or any(c in leaf for c in "\\:\x00"):
        raise ValueError("invalid bin member")
    return leaf


def extract_bin(archive, destination):
    destination.mkdir()
    seen = set()
    total = 0

    def save(name, size, mode, stream):
        nonlocal total
        key = name.casefold()
        if key in seen or size < 0 or size > 128 * 1024 * 1024:
            raise ValueError("invalid or duplicate package member")
        seen.add(key)
        total += size
        if total > 1024 * 1024 * 1024:
            raise ValueError("package bin exceeds limit")
        path = destination / name
        with path.open("xb") as output:
            shutil.copyfileobj(stream, output)
        if path.stat().st_size != size:
            raise ValueError("member size mismatch")
        path.chmod(mode & 0o777)

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                name = bin_name(member.filename)
                if name is None or member.is_dir():
                    continue
                mode = member.external_attr >> 16
                if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                    raise ValueError("non-regular bin member")
                with package.open(member) as stream:
                    save(name, member.file_size, mode or 0o644, stream)
    else:
        with tarfile.open(archive, "r:gz") as package:
            for member in package:
                name = bin_name(member.name)
                if name is None or member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError("non-regular bin member")
                with package.extractfile(member) as stream:
                    save(name, member.size, member.mode, stream)


def run(command, evidence, label, env=None, cwd=ROOT, check=True, timeout=600):
    with (evidence / (label + ".log")).open("wb") as log:
        return subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                              check=check, timeout=timeout).returncode


def probe_environment(environment):
    # Keep ordinary host discovery, but don't inherit runtime instrumentation,
    # additional code/deps, or globalization overrides. Record names, not values.
    prefixes = ("COMPLUS_", "CORECLR_", "COR_", "COREHOST_", "LD_", "DYLD_")
    allowed_dotnet = {"DOTNET_ROOT", "DOTNET_ROOT_X64", "DOTNET_ROOT_ARM64",
                      "DOTNET_ROOT(X86)", "DOTNET_CLI_HOME"}
    removed = sorted(key for key in environment if key.upper().startswith(prefixes)
                     or key.upper() in {"CLR_ICU_VERSION_OVERRIDE", "ICU_DATA",
                         "RUNNER_TEST_GET_REPOSITORY_PATH_FAILSAFE",
                         "GITHUB_ACTIONS_RUNNER_ISSUE_MATCHER_TIMEOUT",
                         "ACTIONS_ALLOW_UNSECURE_STOPCOMMAND_TOKENS"}
                     or (key.upper().startswith("DOTNET_") and key.upper() not in allowed_dotnet))
    return {key: value for key, value in environment.items() if key not in removed}, removed


def extract_break_rules(source):
    """Extract literal strings only from the already digest-verified native source."""
    result = {}
    for name, declaration in (("new", "BreakIteratorRuleNew"), ("old", "BreakIteratorRuleOld")):
        matches = re.findall(r"static const char\* " + declaration + r"\s*=.*?;\n", source, re.S)
        if len(matches) != 1:
            raise ValueError("ambiguous native break rule declaration")
        literals = re.findall(r'"(?:[^"\\]|\\.)*"', matches[0])
        value = "".join(json.loads(token) for token in literals)
        if not value or len(value) > 16384:
            raise ValueError("invalid native break rule text")
        result[name] = value
    return result


def read_break_rules(path):
    return extract_break_rules(path.read_text(encoding="utf-8"))


def verify_context_offsets(value):
    observed = value.get("contextOffsets")
    if (not isinstance(observed, dict) or observed.get("status") != "passed"
            or observed.get("researchOnly") is not True or observed.get("examples") != []
            or "activeCase" in observed or "failedElements" in observed or "activeContextItem" in value):
        raise ValueError("incomplete context-offset observation")
    corpus = observed.get("contextScalars")
    if (not isinstance(corpus, list) or not 0 < len(corpus) <= 100000
            or type(value.get("contextItemCount")) is not int or type(value.get("contextChecks")) is not int
            or len(corpus) != value.get("contextItemCount") or len(corpus) != value.get("contextChecks")
            or any(not isinstance(s, list) or not 0 < len(s) <= 64
                   or any(type(cp) is not int or not 0 < cp <= 0x10ffff or 0xd800 <= cp <= 0xdfff for cp in s)
                   or sum(2 if cp > 0xffff else 1 for cp in s) > 64 for s in corpus)):
        raise ValueError("invalid or incomplete context corpus")
    if (len({tuple(s) for s in corpus}) != len(corpus)
            or any(58 in s for s in corpus)
            or observed.get("corpusSha256") != hashlib.sha256(json.dumps(corpus, separators=(",", ":")).encode("ascii")).hexdigest()):
        raise ValueError("context corpus identity mismatch")
    prefixes = [[], [0x640], [0x7fa], [0x180a], [0x1cd3], [0xfe73]]
    tails = [[], [120], [0x301], [0x200d, 0x301]]
    for key, expected in (("prefixScalars", prefixes), ("tailScalars", tails)):
        actual = observed.get(key)
        if actual != expected or any(type(cp) is not int for s in actual for cp in s):
            raise ValueError("context case shapes changed")
    table = json.loads((ROOT / "tests/runner-package/unicode-candidate.json").read_text(encoding="utf-8"))
    candidates = {cp for start, end in table["ranges"] for cp in range(start, end + 1)}
    if not all(prefix[0] in candidates for prefix in prefixes[1:]):
        raise ValueError("context prefixes outside candidate table")
    starts = sum(s[0] in candidates for s in corpus)
    for key, expected in {"candidateStartContexts": starts, "eligibleChecks": (len(corpus) * 5 + starts) * 4,
                          "outsideChecks": (len(corpus) - starts) * 4, "headerFailures": 0,
                          "zeroWidthNextCount": 0, "separatorFailures": 0}.items():
        if type(observed.get(key)) is not int or observed[key] != expected:
            raise ValueError("incomplete or failed context coverage")
    if (type(observed.get("outsideMoved")) is not int or not 0 <= observed["outsideMoved"] <= observed["outsideChecks"]
            or type(observed.get("elapsedMilliseconds")) is not int or observed["elapsedMilliseconds"] < 0):
        raise ValueError("invalid context counters")


def verify_insertion_offsets(value):
    verify_context_offsets(value)
    observed = value.get("insertionOffsets")
    if (not isinstance(observed, dict) or observed.get("status") != "passed"
            or observed.get("researchOnly") is not True or observed.get("examples") != []
            or any(key in observed for key in ("activeScalar", "activeControl", "activeCase", "failedElements"))):
        raise ValueError("incomplete insertion-offset observation")
    context = value["contextOffsets"]
    if observed.get("corpusSha256") != context["corpusSha256"] or [0x438, 0x306] not in context["contextScalars"]:
        raise ValueError("insertion context identity mismatch")
    properties = [[0x327, 202], [0x306, 230], [0x300, 230], [0x438, 0], [88, 0], [0x34f, 0], [0x200d, 0], [120, 0]]
    if (observed.get("propertyControls") != properties
            or any(type(v) is not int for pair in observed["propertyControls"] for v in pair)
            or observed.get("extraScalars") != [0x34f, 0x200d, 120]
            or any(type(v) is not int for v in observed["extraScalars"])):
        raise ValueError("insertion property controls changed")
    marks = observed.get("nonstarters")
    if (not isinstance(marks, list) or not 0 < len(marks) <= 4096
            or any(not isinstance(p, list) or len(p) != 2 or any(type(v) is not int for v in p)
                   or not 0 < p[0] <= 0x10ffff or 0xd800 <= p[0] <= 0xdfff or not 0 < p[1] <= 255 for p in marks)):
        raise ValueError("invalid insertion nonstarter corpus")
    scalars = [p[0] for p in marks]
    if (scalars != sorted(set(scalars))
            or any((dict(marks).get(cp) != lead if lead else cp in scalars) for cp, lead in properties)
            or observed.get("nonstarterSha256") != hashlib.sha256(json.dumps(marks, separators=(",", ":")).encode("ascii")).hexdigest()):
        raise ValueError("insertion nonstarter identity mismatch")
    table = json.loads((ROOT / "tests/runner-package/unicode-candidate.json").read_text(encoding="utf-8"))
    candidates = {cp for start, end in table["ranges"] for cp in range(start, end + 1)}
    positions = sum(len(s) - 1 for s in context["contextScalars"])
    candidate_positions = sum(len(s) - 1 for s in context["contextScalars"] if s[0] in candidates)
    if 0x438 not in candidates:
        raise ValueError("insertion control outside candidate table")
    count = len(marks) + 3
    if positions <= 0 or 6 * positions * count > 20000000:
        raise ValueError("insertion case bound exceeded")
    for key, expected in {"scalarChecks": 1112063, "controlLoopChecks": 1, "insertionPositions": positions, "candidatePositions": candidate_positions,
                          "eligibleChecks": (5 * positions + candidate_positions) * count,
                          "outsideChecks": (positions - candidate_positions) * count,
                          "headerFailures": 0, "zeroWidthNextCount": 0, "separatorFailures": 0}.items():
        if type(observed.get(key)) is not int or observed[key] != expected:
            raise ValueError("incomplete or failed insertion coverage")
    if (type(observed.get("outsideMoved")) is not int or not 0 <= observed["outsideMoved"] <= observed["outsideChecks"]
            or type(observed.get("elapsedMilliseconds")) is not int or observed["elapsedMilliseconds"] < 0
            or type(observed.get("laterZeroWidthCases")) is not int or not 0 < observed["laterZeroWidthCases"] <= observed["eligibleChecks"]):
        raise ValueError("invalid insertion counters")
    controls = observed.get("controls")
    texts = ["\u0438\u0327\u0306", "\u0438\u0306\u0327", "\u0438\u0300\u0306", "\u0438X\u0306"]
    if (not isinstance(controls, list) or len(controls) != 4 or any(not isinstance(c, dict) for c in controls)
            or [c.get("text") for c in controls] != texts):
        raise ValueError("missing insertion offset controls")
    expected_offsets = [[(0, 3), (3, 3)], [(0, 2), (2, 3)], [(0, 1), (1, 2), (2, 3)], [(0, 1), (1, 2), (2, 3)]]
    for control, offsets in zip(controls, expected_offsets):
        elements = control.get("elements")
        if (not isinstance(elements, list) or len(elements) != len(offsets)
                or any(not isinstance(e, dict) or set(e) != {"value", "low", "high"}
                       or any(type(v) is not int for v in e.values())
                       or not -(2 ** 31) <= e["value"] < 2 ** 31 or e["value"] in (-1, 0) for e in elements)
                or [(e["low"], e["high"]) for e in elements] != offsets):
            raise ValueError("invalid insertion control elements")
    if [e["value"] for e in controls[0]["elements"]] != [e["value"] for e in controls[1]["elements"]]:
        raise ValueError("insertion reordered control mismatch")
    header = observed.get("headerControl")
    if (not isinstance(header, dict) or header.get("data") != texts[0]
            or type(header.get("separator")) is not int or header["separator"] != 9):
        raise ValueError("missing in-header insertion control")
    elements = header.get("elements")
    if (not isinstance(elements, list) or not 11 <= len(elements) < 128
            or any(not isinstance(e, dict) or set(e) != {"value", "low", "high"}
                   or any(type(v) is not int for v in e.values()) or not -(2 ** 31) <= e["value"] < 2 ** 31
                   or e["value"] == -1 or not 0 <= e["low"] <= e["high"] <= 19 for e in elements)
            or [(e["low"], e["high"]) for e in elements[:9]] != [(i, i + 1) for i in range(9)]
            or any(e["value"] == 0 for e in elements[:9]) or elements[7]["value"] != elements[8]["value"]
            or elements[-1]["high"] != 19
            or any(a["high"] != b["low"] for a, b in zip(elements, elements[1:]))
            or elements[9:11] != [{"value": e["value"], "low": e["low"] + 9, "high": e["high"] + 9}
                                  for e in controls[0]["elements"]]):
        raise ValueError("invalid in-header insertion control elements")


def verify_ce_offsets(value):
    attributes = value.get("collatorAttributes")
    expected = {"french": 16, "alternate": 21, "caseFirst": 16, "caseLevel": 16,
                "normalization": 16, "strength": 2, "hiragana": 16, "numeric": 16}
    if (not isinstance(attributes, dict) or attributes != expected
            or any(type(v) is not int for v in attributes.values())
            or value.get("searchCollatorMatches") is not True
            or type(value.get("searchElementComparison")) is not int
            or value["searchElementComparison"] != 2):
        raise ValueError("unobserved or unexpected collator/search settings")
    offsets = value.get("ceOffsets")
    if not isinstance(offsets, dict):
        raise ValueError("missing CE-offset observation")
    prefixes = offsets.get("prefixes")
    if (offsets.get("status") != "passed" or offsets.get("researchOnly") is not True
            or prefixes != [0x640, 0x7fa, 0x180a, 0x1cd3, 0xfe73]
            or any(type(cp) is not int for cp in prefixes)
            or type(value.get("emptyEquivalentCount")) is not int or value["emptyEquivalentCount"] != len(prefixes)
            or value.get("emptyEquivalentExamples") != prefixes
            or offsets.get("examples") != []):
        raise ValueError("incomplete CE-offset observation")
    for key, expected in {"candidateChecks": 142081, "pairChecks": 5560315,
                          "delimiterFailures": 0, "zeroWidthNextCount": 0, "separatorFailures": 0}.items():
        if type(offsets.get(key)) is not int or offsets[key] != expected:
            raise ValueError("incomplete or failed finite CE-offset coverage")
    if (type(offsets.get("skippedZeroCases")) is not int or not 0 < offsets["skippedZeroCases"] <= 5702396
            or type(offsets.get("elapsedMilliseconds")) is not int or offsets["elapsedMilliseconds"] < 0):
        raise ValueError("missing CE skip/timing evidence")
    samples = offsets.get("samples")
    data = ["日", "😀", "\u0640x", "\u07fax", "\u180ax", "\u1cd3x", "\ufe73x", "\u0640\u0301", "\u0301"]
    if (not isinstance(samples, list) or any(not isinstance(s, dict) for s in samples)
            or [s.get("data") for s in samples] != data):
        raise ValueError("missing CE-offset samples/control")
    for sample in samples:
        separator = sample.get("separator")
        if type(separator) is not int or separator != (12 if sample["data"] == "\u0301" else 9):
            raise ValueError("CE-offset sample/control mismatch")
        elements = sample.get("elements")
        length = 2 + len(sample["data"].encode("utf-16-le")) // 2
        if (not isinstance(elements, list) or not 3 <= len(elements) < 128
                or any(not isinstance(e, dict) or set(e) != {"value", "low", "high"}
                       or any(type(v) is not int for v in e.values())
                       or not -(2 ** 31) <= e["value"] < 2 ** 31 or e["value"] == -1
                       or not 0 <= e["low"] <= e["high"] <= length
                       for e in elements)):
            raise ValueError("invalid CE-offset sample elements")
        if any(element["low"] != previous["high"] for previous, element in zip(elements, elements[1:])):
            raise ValueError("discontinuous sample CE offsets")
        if (elements[0]["low"] != 0 or elements[0]["high"] != 1 or elements[0]["value"] == 0
                or elements[1] != {"value": elements[0]["value"], "low": 1, "high": 2}):
            raise ValueError("invalid sample delimiter elements")
        retained = next((e for e in elements[2:] if e["value"] != 0), None)
        if retained is None or not 2 <= retained["low"] < retained["high"]:
            raise ValueError("invalid sample retained element")
        if ord(sample["data"][0]) in prefixes and elements[2] != {"value": 0, "low": 2, "high": 3}:
            raise ValueError("sample raw-zero prefix not observed")
    control = offsets.get("expansionControl")
    if (not isinstance(control, dict) or control.get("text") != "\u00e5a" or control.get("pattern") != "a"
            or type(control.get("index")) is not int or control["index"] != 1):
        raise ValueError("missing partial-expansion control")
    elements = control.get("elements")
    if (not isinstance(elements, list) or len(elements) != 3
            or any(not isinstance(e, dict) or set(e) != {"value", "low", "high"}
                   or any(type(v) is not int for v in e.values())
                   or not -(2 ** 31) <= e["value"] < 2 ** 31 or e["value"] in (-1, 0) for e in elements)
            or [(e["low"], e["high"]) for e in elements] != [(0, 1), (1, 1), (1, 2)]
            or elements[0]["value"] != elements[2]["value"]):
        raise ValueError("partial-expansion CE control mismatch")


def verify_collation(probe, rules_sha):
    if not isinstance(rules_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", rules_sha):
        raise ValueError("invalid break rules resource identity")
    if probe.get("collationResearchStatus") != "passed":
        raise ValueError("incomplete native collation observation")
    cultures = probe.get("cultures")
    if not isinstance(cultures, list) or any(not isinstance(c, dict) for c in cultures) or [c.get("culture") for c in cultures] != ["", "en-US"]:
        raise ValueError("incomplete native collation cultures")
    source_sha = next(s["sha256"] for s in json.loads(PINS.read_text())["sources"] if s["name"] == "pal_collation.c")
    for culture in probe["cultures"]:
        value = culture.get("collationObservation", {})
        verify_ce_offsets(value)
        verify_insertion_offsets(value)
        actual_hash = value.get("actualRuleSha256", "")
        compiled = value.get("compiledRules", {})
        old = compiled.get("old")
        if not isinstance(old, dict) or type(old.get("error")) is not int or "sha256" not in old:
            raise ValueError("missing old break rule observation")
        old_hash = old["sha256"]
        if old["error"] <= 0:
            if not isinstance(old_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", old_hash) or old_hash == actual_hash:
                raise ValueError("invalid or ambiguous old break rule observation")
        elif old_hash is not None:
            raise ValueError("failed old break rule compilation has a digest")
        empty_count = value.get("emptyEquivalentCount")
        empty_examples = value.get("emptyEquivalentExamples")
        if (type(empty_count) is not int or not 0 <= empty_count <= 142081
                or not isinstance(empty_examples, list) or len(empty_examples) != min(16, empty_count)
                or any(type(cp) is not int or not 0 <= cp <= 0x10ffff or 0xd800 <= cp <= 0xdfff for cp in empty_examples)
                or len(set(empty_examples)) != len(empty_examples)):
            raise ValueError("incomplete empty-equivalent observation")
        if (value.get("status") != "passed" or value.get("researchOnly") is not True
                or value.get("culture") != culture["culture"]
                or value.get("icuVersionRaw", 0) != (culture.get("icu") or {}).get("versionRaw")
                or not value.get("icuVersionRaw") or value.get("externalBreakIterator") is not True
                or value.get("selectedRules") != "new" or not re.fullmatch(r"[0-9a-f]{64}", actual_hash)
                or compiled.get("new", {}).get("sha256") != actual_hash
                or compiled.get("new", {}).get("error", 1) > 0
                or value.get("ruleSourceSha256") != source_sha
                or value.get("ruleResourceSha256") != rules_sha
                or value.get("tableSha256") != digest(ROOT / "tests/runner-package/unicode-candidate.json")
                or value.get("scalarChecks") != 142081 or value.get("colonContextCount") != 0
                or value.get("missingNfdBoundaryCount") != 0 or value.get("unexpectedGcbCount") != 0
                or not 0 < value.get("contextItemCount", 0) <= 100000
                or value.get("contextChecks") != value.get("contextItemCount")
                or not value.get("commonLibrary") or not value.get("internationalLibrary")):
            raise ValueError("incomplete native collation coverage")


def verify_coverage(probe, evidence):
    if probe.get("unicodeResearchStatus") != "passed":
        raise ValueError("incomplete Unicode research")
    cultures = probe["cultures"]
    if [culture["culture"] for culture in cultures] != ["", "en-US"]:
        raise ValueError("unexpected culture coverage")
    for culture in cultures:
        unicode = culture.get("unicodeCandidate", {})
        if (unicode.get("unicodeVersion") != "14.0.0" or unicode.get("researchOnly") is not True
                or unicode.get("tableSha256") != digest(ROOT / "tests/runner-package/unicode-candidate.json")
                or unicode.get("candidateCount") != 142081 or unicode.get("candidateChecks") != 1704972
                or unicode.get("pairChecks") != 11120630 or unicode.get("suffixChecks") != 500
                or unicode.get("failures") != 0
                or unicode.get("examples") != []):
            raise ValueError("incomplete Unicode candidate evidence")
        if culture.get("scalarChecks") != 17793008:
            raise ValueError("incomplete scalar coverage")
        for kind in ("mask", "annotation"):
            count = len(json.loads((evidence / f"{kind}-corpus.json").read_text()))
            if count == 0 or culture.get(f"{kind}Cases") != count:
                raise ValueError("incomplete corpus coverage")
            if culture.get("workerEffects", {}).get(f"{kind}Cases") != count:
                raise ValueError("incomplete worker corpus coverage")
        effects = culture.get("workerEffects", {})
        if effects.get("stoppedCases") != 4 or effects.get("echoAndMaskedAnnotationCases") != 1:
            raise ValueError("incomplete worker state coverage")
        research = culture.get("unicodeWorkerEffects", {})
        if (research.get("researchOnly") is not True or research.get("observedCulture") != culture["culture"]
                or research.get("negativeControlCases") != 2 or research.get("maskCases") != 120
                or research.get("annotationCases") != 180 or research.get("stoppedCases") != 40
                or research.get("maskedAnnotationCases") != 10):
            raise ValueError("incomplete Unicode worker evidence")


def verify_coreclr(trace, binary, rid):
    matches = re.findall(r"^CoreCLR path = '(.*)', CoreCLR dir = ", trace, re.MULTILINE)
    name = {"linux-x64": "libcoreclr.so", "osx-arm64": "libcoreclr.dylib", "win-x64": "coreclr.dll"}[rid]
    if len(matches) != 1 or Path(matches[0]).resolve() != (binary / name).resolve():
        raise ValueError("host did not select package CoreCLR")
    return name


def verify_managed(probe, files, pins):
    identities = probe.get("loadedManagedAssemblies")
    core, parser, worker = probe.get("coreLibrary"), probe.get("parserAssembly"), probe.get("workerAssembly")
    masker = probe.get("maskerAssembly")
    if not isinstance(identities, list) or not identities or not core or not parser or not worker or not masker:
        raise ValueError("incomplete loaded assembly evidence")
    for identity in [core, parser, worker, masker, *identities]:
        if (not isinstance(identity, dict) or identity.get("inPackage") is not True
                or identity.get("file") not in files
                or files[identity["file"]] != identity.get("sha256")):
            raise ValueError("loaded assembly differs from package")
    if core.get("informationalVersion") != f'{pins["runtimeVersion"]}+{pins["runtimeCommit"]}':
        raise ValueError("runtime build differs from inspected source")
    if parser.get("informationalVersion") != f'{pins["runnerVersion"]}+{pins["runnerCommit"]}':
        raise ValueError("parser build differs from pinned Runner source")
    if worker.get("informationalVersion") != f'{pins["runnerVersion"]}+{pins["runnerCommit"]}':
        raise ValueError("worker build differs from pinned Runner source")
    allowed_dynamic = ["ProxyBuilder, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null"]
    dynamic = probe.get("dynamicAssemblyNames")
    # An earlier parser/culture failure can occur before the first service
    # double is created. Don't mislabel that as a foreign-assembly failure.
    if dynamic not in ([], allowed_dynamic) or (probe.get("status") == "passed" and dynamic != allowed_dynamic):
        raise ValueError("unexpected dynamic assembly evidence")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new evidence directory")
    parser.add_argument("--archive", type=Path, help="optional cached archive (still verified)")
    args = parser.parse_args()
    evidence = args.output.resolve()
    evidence.mkdir(parents=True, exist_ok=False)  # Never mix runs or reuse stale results.
    pins = json.loads(PINS.read_text())
    rid = {("Linux", "x86_64"): "linux-x64", ("Darwin", "arm64"): "osx-arm64",
           ("Windows", "AMD64"): "win-x64"}.get((platform.system(), platform.machine()))
    record = {"schemaVersion": 1, "status": "failed", "rid": rid, "pins": pins,
              "scope": "published-package parser and command-effects probe; not a live Worker process",
              "githubRunId": os.environ.get("GITHUB_RUN_ID"),
              "githubSha": os.environ.get("GITHUB_SHA"),
              "imageOS": os.environ.get("ImageOS"), "imageVersion": os.environ.get("ImageVersion")}
    try:
        if rid not in pins["packages"]:
            raise ValueError("unsupported package probe platform")
        record["pythonVersion"] = platform.python_version()
        record["sourceDigests"] = {name: digest(ROOT / name) for name in (
            "scripts/test-runner-package.py", "tests/runner-package/test_harness.py", "tests/runner-package/Program.cs", "tests/runner-package/WorkerProbe.cs", "tests/runner-package/Probe.csproj",
            "tests/runner-package/UnicodeCandidateProbe.cs", "tests/runner-package/CollationProbe.cs", "tests/runner-package/unicode-candidate.json",
            "tests/runner-package/unicode-pins.json", "tests/runner-package/UNICODE-LICENSE.txt",
            "scripts/generate-unicode-candidate.py")}
        record["rustcVersion"] = subprocess.check_output(["rustc", "--version"], cwd=ROOT, text=True).strip()
        with tempfile.TemporaryDirectory(prefix="shoutx-runner-package-") as temporary:
            work = Path(temporary).resolve()
            record["phase"] = "select-sdk"
            # Hosted images contain newer SDKs too; setup-dotnet does not select
            # a default. Keep the selection local, with no repository-wide change.
            (work / "global.json").write_text(json.dumps({"sdk": {
                "version": pins["sdkVersion"], "rollForward": "disable"}}))
            sdk = subprocess.check_output(["dotnet", "--version"], cwd=work, text=True).strip()
            record["buildSdk"] = sdk
            if sdk != pins["sdkVersion"]:
                raise ValueError("unexpected build SDK")
            record["phase"] = "verify-package"
            pin = pins["packages"][rid]
            name = f'actions-runner-{rid}-{pins["runnerVersion"]}.{pin["extension"]}'
            url = f'https://github.com/actions/runner/releases/download/v{pins["runnerVersion"]}/{name}'
            archive = work / name
            if args.archive:
                shutil.copyfile(args.archive.resolve(), archive)
            else:
                download(url, archive, pin["size"])
            verify(archive, pin["sha256"], pin["size"])
            record["package"] = {"url": url, "sha256": digest(archive), "size": archive.stat().st_size}
            binary = work / "bin"
            extract_bin(archive, binary)
            files = {p.name: digest(p) for p in sorted(binary.iterdir())}
            (evidence / "package-bin-sha256.json").write_text(json.dumps(files, indent=2) + "\n")
            config = json.loads((binary / "Runner.Worker.runtimeconfig.json").read_text())
            record["workerRuntimeConfig"] = config
            expected = [{"name": "Microsoft.NETCore.App", "version": pins["runtimeVersion"]}]
            if config["runtimeOptions"].get("includedFrameworks") != expected or "framework" in config["runtimeOptions"]:
                raise ValueError("unexpected worker runtime config")
            for source in pins["sources"]:
                path = work / source["name"]
                download(source["url"], path, 1024 * 1024)
                verify(path, source["sha256"])
                shutil.copyfile(path, evidence / source["name"])
            break_rules = read_break_rules(work / "pal_collation.c")
            break_rules["sourceSha256"] = digest(work / "pal_collation.c")
            (evidence / "break-rules.json").write_text(json.dumps(break_rules, indent=2) + "\n")
            record["breakRulesSha256"] = digest(evidence / "break-rules.json")
            record["phase"] = "verify-unicode-research-sources"
            unicode_pins = json.loads((ROOT / "tests/runner-package/unicode-pins.json").read_text())
            for source in unicode_pins["sources"]:
                path = work / source["name"]
                download(source["url"], path, 4 * 1024 * 1024)
                verify(path, source["sha256"])
            run([sys.executable, str(ROOT / "scripts/generate-unicode-candidate.py"),
                 "--source-dir", str(work), "--check"], evidence, "unicode-generation")
            shutil.copyfile(ROOT / "tests/runner-package/unicode-candidate.json", evidence / "unicode-candidate.json")
            shutil.copyfile(ROOT / "tests/runner-package/unicode-pins.json", evidence / "unicode-pins.json")
            shutil.copyfile(ROOT / "tests/runner-package/UNICODE-LICENSE.txt", evidence / "UNICODE-LICENSE.txt")
            record["phase"] = "build-probe-and-corpora"
            for kind in ("mask", "annotation"):
                env = os.environ.copy()
                env["CARGO_TARGET_DIR"] = str(work / "cargo")
                env[f"SHOUTX_{kind.upper()}_CORPUS_PATH"] = str(evidence / f"{kind}-corpus.json")
                run(["cargo", "test", "--locked", "--features", "unstable-github-actions-stdout",
                     "--test", f"{kind}_runner_fixture", f"export_{kind}_corpus", "--", "--ignored"],
                    evidence, f"generate-{kind}", env)
            run(["dotnet", "build", str(ROOT / "tests/runner-package/Probe.csproj"), "-c", "Release",
                 "-nodeReuse:false", "-p:UseSharedCompilation=false",
                 f"-p:RunnerBin={binary}", f"-p:BreakRulesPath={evidence / 'break-rules.json'}", f"-p:BaseIntermediateOutputPath={work / 'obj'}/",
                 "-o", str(work / "probe")], evidence, "build-probe", cwd=work)
            shutil.copyfile(work / "probe/Probe.dll", binary / "Probe.dll")
            record["probeSha256"] = digest(binary / "Probe.dll")
            # Self-contained worker config selects local hostpolicy/coreclr, not SDK runtime.
            probe_env, record["removedEnvironmentNames"] = probe_environment(os.environ)
            probe_env["COREHOST_TRACE"] = "1"
            probe_env["COREHOST_TRACEFILE"] = str(evidence / "corehost.log")
            record["phase"] = "execute-probe"
            exit_code = run(["dotnet", "exec", "--runtimeconfig", str(binary / "Runner.Worker.runtimeconfig.json"),
                 "--depsfile", str(binary / "Runner.Worker.deps.json"), str(binary / "Probe.dll"),
                 str(evidence / "probe.json"), str(evidence / "mask-corpus.json"),
                 str(evidence / "annotation-corpus.json")], evidence, "execute-probe", probe_env, cwd=work, check=False, timeout=900)
            record["probeExitCode"] = exit_code
            record["phase"] = "verify-loaded-identities"
            trace = (evidence / "corehost.log").read_text(encoding="utf-8")
            record["launcherHostFxr"] = re.findall(r"^Resolved fxr \[(.*)\]", trace, re.MULTILINE)
            record["launcherHostFxrBuild"] = re.findall(r"^--- Invoked hostfxr_main_startupinfo \[(.*)\]", trace, re.MULTILINE)
            coreclr = verify_coreclr(trace, binary, rid)
            record["selectedCoreClr"] = {"file": coreclr, "sha256": files[coreclr]}
            record["corehostTraceSha256"] = digest(evidence / "corehost.log")
            probe = json.loads((evidence / "probe.json").read_text())
            record["unicodeResearchStatus"] = probe.get("unicodeResearchStatus")
            record["collationResearchStatus"] = probe.get("collationResearchStatus")
            verify_managed(probe, files, pins)
            record["icuSourcePreconditionsByCulture"] = [
                {"culture": c["culture"], "observed": c["icuSourcePreconditionsObserved"]}
                for c in probe.get("cultures", [])]
            if {p.name for p in binary.iterdir()} != set(files) | {"Probe.dll"}:
                raise ValueError("unexpected package directory additions")
            for name, sha in files.items():
                if digest(binary / name) != sha:
                    raise ValueError("package binary changed during probe")
            if exit_code != 0 or probe["status"] != "passed":
                raise ValueError("probe did not pass")
            verify_coverage(probe, evidence)
            verify_collation(probe, record["breakRulesSha256"])
            record["phase"] = "cleanup"
        record["status"] = "passed"
        record["phase"] = "complete"
    except Exception as error:
        record["errorType"] = type(error).__name__
        if isinstance(error, ValueError):
            record["errorRule"] = str(error)
        print("Runner package evidence failed; inspect the evidence directory.")
        return 1
    finally:
        (evidence / "evidence.json").write_text(json.dumps(record, indent=2) + "\n")
    print("Runner package evidence passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
