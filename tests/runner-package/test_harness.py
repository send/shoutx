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


class HarnessTests(unittest.TestCase):
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
            return {"status": "passed", "researchOnly": True, "culture": culture,
                    "icuVersionRaw": 123, "externalBreakIterator": True, "selectedRules": "new",
                    "actualRuleSha256": "a" * 64, "compiledRules": {"new": {"sha256": "a" * 64, "error": 0}},
                    "ruleSourceSha256": source_sha, "tableSha256": harness.digest(harness.ROOT / "tests/runner-package/unicode-candidate.json"),
                    "scalarChecks": 142081, "colonContextCount": 0, "missingNfdBoundaryCount": 0,
                    "unexpectedGcbCount": 0, "contextItemCount": 100, "contextChecks": 100,
                    "emptyEquivalentCount": 0, "emptyEquivalentExamples": [],
                    "commonLibrary": "common", "internationalLibrary": "international"}
        report = {"collationResearchStatus": "passed", "cultures": [
            {"culture": name, "icu": {"versionRaw": 123}, "collationObservation": observation(name)}
            for name in ("", "en-US")]}
        harness.verify_collation(report)
        for status in (None, "incomplete", "failed"):
            with self.assertRaises(ValueError):
                harness.verify_collation({**report, "collationResearchStatus": status})
        with self.assertRaises(ValueError):
            harness.verify_collation({**report, "cultures": []})
        for field in observation(""):
            bad = json.loads(json.dumps(report))
            del bad["cultures"][0]["collationObservation"][field]
            with self.assertRaises(ValueError, msg=field):
                harness.verify_collation(bad)
        for field, value in (("selectedRules", "old"), ("externalBreakIterator", False),
                             ("icuVersionRaw", 456), ("colonContextCount", 1),
                             ("missingNfdBoundaryCount", 1), ("unexpectedGcbCount", 1),
                             ("actualRuleSha256", "b" * 64), ("contextChecks", 99),
                             ("emptyEquivalentCount", 1), ("emptyEquivalentExamples", [0x301]),
                             ("compiledRules", {"new": {"sha256": "a" * 64, "error": 1}})):
            bad = json.loads(json.dumps(report))
            bad["cultures"][1]["collationObservation"][field] = value
            with self.assertRaises(ValueError, msg=field):
                harness.verify_collation(bad)

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
