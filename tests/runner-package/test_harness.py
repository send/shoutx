"""Offline safety/regression checks for the package evidence harness."""
import importlib.util
import io
import json
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/test-runner-package.py"
spec = importlib.util.spec_from_file_location("runner_package", SCRIPT)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
generator_spec = importlib.util.spec_from_file_location("unicode_candidate", SCRIPT.with_name("generate-unicode-candidate.py"))
generator = importlib.util.module_from_spec(generator_spec)
generator_spec.loader.exec_module(generator)


def unicode_evidence():
    return {"unicodeVersion": "14.0.0", "researchOnly": True,
            "tableSha256": harness.digest(harness.ROOT / "tests/runner-package/unicode-candidate.json"),
            "candidateCount": 142081, "candidateChecks": 1704972, "pairChecks": 11120630,
            "suffixChecks": 500, "failures": 0, "examples": []}


def ce_evidence():
    prefixes = [0x640, 0x7fa, 0x180a, 0x1cd3, 0xfe73]
    samples = []
    for data in ["日", "😀", "\u0640x", "\u07fax", "\u180ax", "\u1cd3x", "\ufe73x", "\u0640\u0301", "\u0301"]:
        elements = [{"value": 123, "low": 0, "high": 1}, {"value": 123, "low": 1, "high": 2}]
        low = 2
        if ord(data[0]) in prefixes:
            elements.append({"value": 0, "low": 2, "high": 3})
            low = 3
        elements.append({"value": 456, "low": low, "high": 2 + len(data.encode("utf-16-le")) // 2})
        samples.append({"data": data, "separator": 12 if data == "\u0301" else 9, "elements": elements})
    return {"searchCollatorMatches": True, "searchElementComparison": 2,
            "emptyEquivalentCount": 5, "emptyEquivalentExamples": prefixes,
            "collatorAttributes": {"french": 16, "alternate": 21, "caseFirst": 16, "caseLevel": 16,
                                   "normalization": 16, "strength": 2, "hiragana": 16, "numeric": 16},
            "ceOffsets": {"status": "passed", "researchOnly": True,
                          "prefixes": [0x640, 0x7fa, 0x180a, 0x1cd3, 0xfe73],
                          "candidateChecks": 142081, "pairChecks": 5560315,
                          "delimiterFailures": 0, "zeroWidthNextCount": 0, "separatorFailures": 0,
                          "skippedZeroCases": 5, "elapsedMilliseconds": 100,
                          "examples": [], "samples": samples,
                          "expansionControl": {"text": "\u00e5a", "pattern": "a", "index": 1,
                                               "elements": [{"value": 123, "low": 0, "high": 1},
                                                            {"value": 456, "low": 1, "high": 1},
                                                            {"value": 123, "low": 1, "high": 2}]}}}


class HarnessTests(unittest.TestCase):
    def test_ce_observation_is_fail_closed(self):
        good = ce_evidence()
        harness.verify_ce_offsets(good)
        # Delete every setting and evidence field, including sample internals.
        paths = [[key] for key in good]
        paths += [["collatorAttributes", key] for key in good["collatorAttributes"]]
        paths += [["ceOffsets", key] for key in good["ceOffsets"]]
        paths += [["ceOffsets", "samples", 0, key] for key in ("data", "separator", "elements")]
        paths += [["ceOffsets", "samples", 0, "elements", 0, key] for key in ("value", "low", "high")]
        paths += [["ceOffsets", "expansionControl", key] for key in ("text", "pattern", "index", "elements")]
        for path in paths:
            bad = json.loads(json.dumps(good))
            parent = bad
            for part in path[:-1]:
                parent = parent[part]
            del parent[path[-1]]
            with self.assertRaises(ValueError, msg=str(path)):
                harness.verify_ce_offsets(bad)
        changes = [(["searchCollatorMatches"], False), (["searchElementComparison"], 0),
                   (["collatorAttributes", "normalization"], 17), (["collatorAttributes", "strength"], 15),
                   (["collatorAttributes", "alternate"], 20), (["ceOffsets"], None),
                   (["emptyEquivalentCount"], 6), (["emptyEquivalentExamples"], [0x640])]
        changes += [(["ceOffsets", key], value) for key, value in (
            ("status", "incomplete"), ("researchOnly", False), ("prefixes", []),
            ("candidateChecks", 142080), ("pairChecks", 5560314), ("delimiterFailures", 1),
            ("zeroWidthNextCount", 1), ("separatorFailures", 1), ("separatorFailures", False),
            ("examples", [{}]), ("samples", []), ("skippedZeroCases", 0),
            ("skippedZeroCases", 5702397), ("elapsedMilliseconds", -1))]
        changes += [(["ceOffsets", "samples", 8, "separator"], 9),
                    (["ceOffsets", "samples", 0, "elements", 0, "high"], 100),
                    (["ceOffsets", "samples", 0, "elements", 0, "value"], -1),
                    (["ceOffsets", "samples", 0, "elements", 0, "low"], False),
                    (["ceOffsets", "samples", 0, "elements", 2, "high"], 2),
                    (["ceOffsets", "samples", 0, "elements", 2, "low"], 4),
                    (["ceOffsets", "samples", 0, "elements", 2, "low"], 1),
                    (["ceOffsets", "samples", 0, "elements", 2, "value"], 0),
                    (["ceOffsets", "samples", 2, "elements", 2, "value"], 789),
                    (["ceOffsets", "expansionControl", "text"], "aa"),
                    (["ceOffsets", "expansionControl", "pattern"], "b"),
                    (["ceOffsets", "expansionControl", "index"], 0),
                    (["ceOffsets", "expansionControl", "elements", 2, "value"], 789),
                    (["ceOffsets", "expansionControl", "elements", 1, "high"], 2),
                    (["ceOffsets", "expansionControl", "elements", 1, "value"], 0)]
        for path, value in changes:
            bad = json.loads(json.dumps(good))
            parent = bad
            for part in path[:-1]:
                parent = parent[part]
            parent[path[-1]] = value
            with self.assertRaises(ValueError, msg=str(path)):
                harness.verify_ce_offsets(bad)

    def test_break_rule_source_is_explicit_utf8(self):
        # A full-width 'a' in the pinned source's comments contains byte 0x81,
        # which fails under the Windows CP1252 default.
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "pal_collation.c"
            source = '// \uff41\nstatic const char* BreakIteratorRuleNew = "new";\nstatic const char* BreakIteratorRuleOld = "old";\n'
            path.write_bytes(source.encode("utf-8"))
            original = Path.read_text
            def windows_default(instance, *args, **kwargs):
                kwargs.setdefault("encoding", "cp1252")
                return original(instance, *args, **kwargs)
            with patch.object(Path, "read_text", windows_default):
                with self.assertRaises(UnicodeDecodeError):
                    path.read_text()
                self.assertEqual(harness.read_break_rules(path), {"new": "new", "old": "old"})

    def test_break_rules_extraction_is_bounded_and_unambiguous(self):
        source = 'static const char* BreakIteratorRuleNew = "one\\n" \\\n "two";\nstatic const char* BreakIteratorRuleOld = "old";\n'
        self.assertEqual(harness.extract_break_rules(source), {"new": "one\ntwo", "old": "old"})
        for bad in ("", source + source, source.replace('"old"', '""'),
                    source.replace('"old"', '"' + 'x' * 16385 + '"')):
            with self.assertRaises(ValueError):
                harness.extract_break_rules(bad)

    def test_native_collation_evidence_is_fail_closed(self):
        source_sha = next(s["sha256"] for s in json.loads(harness.PINS.read_text())["sources"] if s["name"] == "pal_collation.c")
        def observation(culture):
            return {**ce_evidence(), "status": "passed", "researchOnly": True, "culture": culture,
                    "icuVersionRaw": 123, "externalBreakIterator": True, "selectedRules": "new",
                    "actualRuleSha256": "a" * 64, "compiledRules": {"new": {"sha256": "a" * 64, "error": 0},
                        "old": {"sha256": "b" * 64, "error": 0}},
                    "ruleSourceSha256": source_sha, "tableSha256": harness.digest(harness.ROOT / "tests/runner-package/unicode-candidate.json"),
                    "ruleResourceSha256": "c" * 64,
                    "scalarChecks": 142081, "colonContextCount": 0, "missingNfdBoundaryCount": 0,
                    "unexpectedGcbCount": 0, "contextItemCount": 100, "contextChecks": 100,
                    "commonLibrary": "common", "internationalLibrary": "international"}
        report = {"collationResearchStatus": "passed", "cultures": [
            {"culture": name, "icu": {"versionRaw": 123}, "collationObservation": observation(name)}
            for name in ("", "en-US")]}
        def verify(report):
            harness.verify_collation(report, "c" * 64)
        verify(report)
        for old in ({"error": 1, "sha256": None}, {"error": -1, "sha256": "b" * 64}):
            valid = json.loads(json.dumps(report))
            valid["cultures"][0]["collationObservation"]["compiledRules"]["old"] = old
            verify(valid)
        for old in (None, {}, {"error": 0}, {"sha256": "b" * 64},
                    {"error": None, "sha256": None}, {"error": True, "sha256": None},
                    {"error": 0, "sha256": None}, {"error": 0, "sha256": "invalid"},
                    {"error": 0, "sha256": "a" * 64}, {"error": -1, "sha256": "a" * 64},
                    {"error": 1, "sha256": "b" * 64}):
            bad = json.loads(json.dumps(report))
            compiled = bad["cultures"][0]["collationObservation"]["compiledRules"]
            if old is None:
                del compiled["old"]
            else:
                compiled["old"] = old
            with self.assertRaises(ValueError):
                verify(bad)
        for rules_sha in (None, "", "d" * 64):
            with self.assertRaises(ValueError):
                harness.verify_collation(report, rules_sha)
        for status in (None, "incomplete", "failed"):
            with self.assertRaises(ValueError):
                verify({**report, "collationResearchStatus": status})
        with self.assertRaises(ValueError):
            verify({**report, "cultures": []})
        for cultures in (None, [{}], [None], list(reversed(report["cultures"]))):
            with self.assertRaises(ValueError):
                verify({**report, "cultures": cultures})
        for field in observation(""):
            bad = json.loads(json.dumps(report))
            del bad["cultures"][0]["collationObservation"][field]
            with self.assertRaises(ValueError, msg=field):
                verify(bad)
        for field, value in (("selectedRules", "old"), ("externalBreakIterator", False),
                             ("icuVersionRaw", 456), ("colonContextCount", 1),
                             ("missingNfdBoundaryCount", 1), ("unexpectedGcbCount", 1),
                             ("actualRuleSha256", "b" * 64), ("contextChecks", 99),
                             ("emptyEquivalentCount", 1), ("emptyEquivalentExamples", [0x301]),
                             ("ruleSourceSha256", "d" * 64), ("ruleResourceSha256", "d" * 64),
                             ("tableSha256", "d" * 64), ("culture", "th-TH"),
                             ("scalarChecks", 142080), ("status", "incomplete"), ("researchOnly", False),
                             ("contextItemCount", 0), ("contextItemCount", 100001),
                             ("compiledRules", {"new": {"sha256": "a" * 64, "error": 1},
                                                "old": {"sha256": "b" * 64, "error": 0}})):
            bad = json.loads(json.dumps(report))
            bad["cultures"][1]["collationObservation"][field] = value
            with self.assertRaises(ValueError, msg=field):
                verify(bad)
        for examples in ([0xd800], [65, 65], [0x110000]):
            bad = json.loads(json.dumps(report))
            value = bad["cultures"][0]["collationObservation"]
            value.update(emptyEquivalentCount=len(examples), emptyEquivalentExamples=examples)
            with self.assertRaises(ValueError):
                verify(bad)

    def test_digest_and_size_must_both_match(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "file"
            path.write_bytes(b"abc")
            sha = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
            harness.verify(path, sha, 3)
            with self.assertRaises(ValueError):
                harness.verify(path, sha, 4)
            with self.assertRaises(ValueError):
                harness.verify(path, "0" * 64, 3)

    def test_only_flat_bin_members_are_selected(self):
        self.assertEqual(harness.bin_name("./bin/core.dll"), "core.dll")
        for path in ("../escape", "/bin/escape", "bin/../escape", "externals/a", "bin/nested/file"):
            self.assertIsNone(harness.bin_name(path))
        for path in ("bin/..", "bin/a\\b", "bin/c:stream"):
            with self.assertRaises(ValueError):
                harness.bin_name(path)

    def test_tar_extracts_regular_files_without_path_interpretation(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            archive = root / "test.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                for name in ("./bin/core.dll", "../escape", "externals/ignored"):
                    entry = tarfile.TarInfo(name)
                    entry.size = 3
                    tar.addfile(entry, io.BytesIO(b"abc"))
            harness.extract_bin(archive, root / "bin")
            self.assertEqual([p.name for p in (root / "bin").iterdir()], ["core.dll"])
            self.assertFalse((root / "escape").exists())
            with self.assertRaises(FileExistsError):
                harness.extract_bin(archive, root / "bin")

    def test_tar_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            archive = root / "test.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                entry = tarfile.TarInfo("bin/link")
                entry.type = tarfile.SYMTYPE
                entry.linkname = "/tmp/escape"
                tar.addfile(entry)
            with self.assertRaises(ValueError):
                harness.extract_bin(archive, root / "bin")

    def test_zip_regular_and_case_collision(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            archive = root / "test.zip"
            with zipfile.ZipFile(archive, "w") as zip_file:
                zip_file.writestr("bin/core.dll", b"abc")
            harness.extract_bin(archive, root / "good")
            self.assertEqual((root / "good/core.dll").read_bytes(), b"abc")
            with zipfile.ZipFile(archive, "a") as zip_file:
                zip_file.writestr("bin/CORE.dll", b"def")
            with self.assertRaises(ValueError):
                harness.extract_bin(archive, root / "bad")

    def test_zip_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            archive = root / "test.zip"
            with zipfile.ZipFile(archive, "w") as zip_file:
                entry = zipfile.ZipInfo("bin/link")
                entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                zip_file.writestr(entry, b"/tmp/escape")
            with self.assertRaises(ValueError):
                harness.extract_bin(archive, root / "bin")

    def test_https_only(self):
        with self.assertRaises(ValueError):
            harness.download("http://example.com/file", Path("unused"), 1)
        with self.assertRaises(ValueError):
            harness.HTTPSRedirect().redirect_request(None, None, 302, "", {}, "http://example.com/")

    def test_host_trace_must_select_package_coreclr(self):
        binary = Path(tempfile.gettempdir()) / "package-bin"
        line = f"CoreCLR path = '{binary / 'libcoreclr.so'}', CoreCLR dir = '{binary}'\n"
        self.assertEqual(harness.verify_coreclr(line, binary, "linux-x64"), "libcoreclr.so")
        for text in ("", line + line, line.replace("package-bin", "sdk-bin")):
            with self.assertRaises(ValueError):
                harness.verify_coreclr(text, binary, "linux-x64")

    def test_runtime_overrides_are_removed_without_recording_values(self):
        original = {"PATH": "/bin", "DOTNET_ROOT": "/sdk", "LANG": "en_US.UTF-8",
                    "DOTNET_STARTUP_HOOKS": "private", "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
                    "COMPlus_ReadyToRun": "0", "CORECLR_ENABLE_PROFILING": "1", "DYLD_INSERT_LIBRARIES": "private",
                    "ICU_DATA": "/private/data", "RUNNER_TEST_GET_REPOSITORY_PATH_FAILSAFE": "1",
                    "GITHUB_ACTIONS_RUNNER_ISSUE_MATCHER_TIMEOUT": "1",
                    "ACTIONS_ALLOW_UNSECURE_STOPCOMMAND_TOKENS": "true"}
        env, removed = harness.probe_environment(original)
        self.assertEqual(env, {"PATH": "/bin", "DOTNET_ROOT": "/sdk", "LANG": "en_US.UTF-8"})
        self.assertEqual(set(removed), set(original) - set(env))
        self.assertIn("DOTNET_STARTUP_HOOKS", original)

    def test_coverage_must_be_complete(self):
        with tempfile.TemporaryDirectory() as root:
            evidence = Path(root)
            for kind in ("mask", "annotation"):
                (evidence / f"{kind}-corpus.json").write_text("[{}]")
            report = {"unicodeResearchStatus": "passed", "cultures": [{"culture": name, "scalarChecks": 17793008,
                                    "unicodeCandidate": unicode_evidence(),
                                    "unicodeWorkerEffects": {"researchOnly": True, "observedCulture": name,
                                                             "negativeControlCases": 2, "maskCases": 120,
                                                             "annotationCases": 180, "stoppedCases": 40,
                                                             "maskedAnnotationCases": 10},
                                    "maskCases": 1, "annotationCases": 1,
                                    "workerEffects": {"maskCases": 1, "annotationCases": 1,
                                                      "stoppedCases": 4, "echoAndMaskedAnnotationCases": 1}}
                                  for name in ("", "en-US")]}
            harness.verify_coverage(report, evidence)
            for field, value in (("researchOnly", False), ("maskCases", 0), ("annotationCases", 0),
                                 ("stoppedCases", 0), ("maskedAnnotationCases", 0),
                                 ("observedCulture", "th-TH"), ("negativeControlCases", 0)):
                bad = json.loads(json.dumps(report))
                bad["cultures"][0]["unicodeWorkerEffects"][field] = value
                with self.assertRaises(ValueError):
                    harness.verify_coverage(bad, evidence)
                del bad["cultures"][0]["unicodeWorkerEffects"][field]
                with self.assertRaises(ValueError):
                    harness.verify_coverage(bad, evidence)
            bad = json.loads(json.dumps(report))
            del bad["cultures"][0]["unicodeWorkerEffects"]
            with self.assertRaises(ValueError):
                harness.verify_coverage(bad, evidence)
            for state in (None, "incomplete", "failed"):
                with self.assertRaises(ValueError):
                    harness.verify_coverage({**report, "unicodeResearchStatus": state}, evidence)
            for field, value in (("unicodeVersion", "15.0.0"), ("researchOnly", False),
                                 ("tableSha256", "wrong"), ("candidateCount", 0), ("candidateChecks", 0),
                                 ("pairChecks", 0), ("suffixChecks", 0), ("failures", 1), ("examples", [{}])):
                bad = json.loads(json.dumps(report))
                bad["cultures"][0]["unicodeCandidate"][field] = value
                with self.assertRaises(ValueError):
                    harness.verify_coverage(bad, evidence)
            bad = json.loads(json.dumps(report))
            del bad["cultures"][0]["unicodeCandidate"]
            with self.assertRaises(ValueError):
                harness.verify_coverage(bad, evidence)
            for field, value in (("scalarChecks", 0), ("maskCases", 0), ("culture", "th-TH")):
                bad = json.loads(json.dumps(report))
                bad["cultures"][0][field] = value
                with self.assertRaises(ValueError):
                    harness.verify_coverage(bad, evidence)
            with self.assertRaises(ValueError):
                harness.verify_coverage({"cultures": []}, evidence)
            for field in ("maskCases", "annotationCases", "stoppedCases", "echoAndMaskedAnnotationCases"):
                bad = json.loads(json.dumps(report))
                bad["cultures"][0]["workerEffects"][field] = 0
                with self.assertRaises(ValueError):
                    harness.verify_coverage(bad, evidence)
            bad = json.loads(json.dumps(report))
            del bad["cultures"][0]["workerEffects"]
            with self.assertRaises(ValueError):
                harness.verify_coverage(bad, evidence)

    def test_managed_identity_is_fail_closed(self):
        pins = {"runtimeVersion": "8", "runtimeCommit": "runtime", "runnerVersion": "2", "runnerCommit": "runner"}
        core = {"file": "core.dll", "sha256": "a", "inPackage": True, "informationalVersion": "8+runtime"}
        parser = {"file": "parser.dll", "sha256": "b", "inPackage": True, "informationalVersion": "2+runner"}
        worker = {"file": "worker.dll", "sha256": "c", "inPackage": True, "informationalVersion": "2+runner"}
        masker = {"file": "Sdk.dll", "sha256": "d", "inPackage": True}
        report = {"status": "passed", "coreLibrary": core, "parserAssembly": parser, "workerAssembly": worker, "maskerAssembly": masker,
                  "loadedManagedAssemblies": [core, parser, worker, masker],
                  "dynamicAssemblyNames": ["ProxyBuilder, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null"]}
        files = {"core.dll": "a", "parser.dll": "b", "worker.dll": "c", "Sdk.dll": "d"}
        harness.verify_managed(report, files, pins)
        harness.verify_managed({**report, "status": "failed", "dynamicAssemblyNames": []}, files, pins)
        for status, names in (("passed", []), ("failed", ["foreign"]), ("failed", None)):
            with self.assertRaises(ValueError):
                harness.verify_managed({**report, "status": status, "dynamicAssemblyNames": names}, files, pins)
        for field, value in (("file", "foreign.dll"), ("sha256", "wrong"), ("inPackage", False), ("informationalVersion", "9+other")):
            bad = json.loads(json.dumps(report))
            bad["coreLibrary"][field] = value
            with self.assertRaises(ValueError):
                harness.verify_managed(bad, files, pins)
        for key in ("parserAssembly", "workerAssembly"):
            bad = json.loads(json.dumps(report))
            bad[key]["informationalVersion"] = "other"
            with self.assertRaises(ValueError):
                harness.verify_managed(bad, files, pins)
        bad = json.loads(json.dumps(report))
        bad["loadedManagedAssemblies"][1]["sha256"] = "other"
        with self.assertRaises(ValueError):
            harness.verify_managed(bad, files, pins)
        for key in ("loadedManagedAssemblies", "coreLibrary", "parserAssembly", "workerAssembly", "maskerAssembly", "dynamicAssemblyNames"):
            bad = dict(report)
            del bad[key]
            with self.assertRaises(ValueError):
                harness.verify_managed(bad, files, pins)
        for key, value in (("dynamicAssemblyNames", ["foreign"]), ("maskerAssembly", {**masker, "sha256": "wrong"})):
            bad = {**report, key: value}
            with self.assertRaises(ValueError):
                harness.verify_managed(bad, files, pins)


class UnicodeCandidateTests(unittest.TestCase):
    def test_positive_categories_ranges_and_exclusions(self):
        data = "0041;A;Lu\n0042;B;Lu\n0043;C;Lu\n0301;MARK;Mn\nE000;PRIVATE;Co\n4E00;<CJK, First>;Lo\n4E02;<CJK, Last>;Lo\n1F3FB;MODIFIER;Sk\n"
        selected = generator.candidates(data, "# @missing: 0000..10FFFF; Other\n0042..0043 ; Prepend # fixture\n1F3FB ; Extend", "0043 ; Default_Ignorable_Code_Point")
        self.assertEqual(selected, [0x41, 0x4e00, 0x4e01, 0x4e02])
        self.assertEqual(generator.ranges(selected), [[0x41, 0x41], [0x4e00, 0x4e02]])

    def test_bad_ranges_and_hashes_fail_closed(self):
        for data in ("4E00;<CJK, First>;Lo", "4E00;<CJK, Last>;Lo", "0041;A;Co"):
            with self.assertRaises(ValueError):
                generator.candidates(data, "", "")
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "UnicodeData.txt").write_text("wrong")
            with self.assertRaises(ValueError):
                generator.generate(Path(directory))

    def test_committed_table_has_expected_membership(self):
        table = json.loads(generator.TABLE.read_text())
        self.assertTrue(table["researchOnly"])
        self.assertEqual(table["unicodeVersion"], "14.0.0")
        points = set()
        previous = 0
        for start, end in table["ranges"]:
            self.assertGreater(start, previous)
            self.assertGreaterEqual(end, start)
            points.update(range(start, end + 1))
            previous = end
        self.assertEqual(len(points), 142081)
        self.assertEqual(table["count"], len(points))
        for cp in (0x65e5, 0x3042, 0x30ab, 0x1f600, 0x1f469, 0x1f44d, 0x627, 0x939, 0xd55c, 0x1f1ef,
                   0xe40, 0xec0, 0x1100, 0x21):
            self.assertIn(cp, points)
        for cp in (0, 0x301, 0xe33, 0xeb3, 0x1f3fb, 0x200d, 0x600, 0x115f, 0xe000, 0xf870, 0x897, 0x11f02, 0xd800):
            self.assertNotIn(cp, points)


if __name__ == "__main__":
    unittest.main()
