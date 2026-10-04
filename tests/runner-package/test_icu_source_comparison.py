import contextlib
import importlib.util
import io
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[2] / 'scripts/compare-icu-generation-sources.py'
spec = importlib.util.spec_from_file_location('comparison', PATH)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class SourceComparisonTests(unittest.TestCase):
    def test_dependency_manifest_shape(self):
        manifest = PATH.parents[1] / 'docs/compatibility/evidence/icu-decoder-source-hashes.txt'
        lines = iter(manifest.read_text().splitlines())
        for name in comparison.DEPENDENCY_PAIRS:
            normalized = set()
            for version in comparison.VERSIONS:
                line = next(lines)
                self.assertRegex(line,
                                 rf'^{re.escape(name)} {re.escape(version)} raw [0-9a-f]{{64}} normalized [0-9a-f]{{64}}$')
                normalized.add(line.split()[5])
            self.assertEqual(next(lines), name + ' normalizedIdentical True')
            self.assertEqual(len(normalized), 1)
        self.assertEqual(list(lines), [])

    def test_dependency_cli_and_function_slice(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for name in comparison.DEPENDENCY_PAIRS:
                for i, version in enumerate(comparison.VERSIONS):
                    source = 'unchanged'
                    if name == 'utrie2.h':
                        source = '#ifdef __cplusplus\nexcluded\n/* Internal definitions ----------------------------------------------------- */\nmacros'
                    if name == 'utrie2.cpp':
                        source = ('outside return ' + str(i) + ';\n'
                                  'U_CAPI UTrie2 * U_EXPORT2\nutrie2_openFromSerialized() { return ' +
                                  ('0' if i == 0 else 'nullptr') + '; }\n'
                                  'U_CAPI UTrie2 * U_EXPORT2\nutrie2_openDummy() { return ' + str(i) + '; }')
                    if name == 'collation.cpp':
                        source = ('outside' + str(i) + '\n'
                                  'uint32_t\nCollation::incThreeBytePrimaryByOffset() {}\n'
                                  'uint32_t\nCollation::decTwoBytePrimaryByOneStep() {' + str(i) + '}\n'
                                  'uint32_t\nCollation::getThreeBytePrimaryForOffsetData() {}\n'
                                  'uint32_t\nCollation::unassignedPrimaryFromCodePoint() {}\n'
                                  'U_NAMESPACE_END\n' + str(i))
                    (folder / f'{name}-{version}').write_bytes(source.encode('utf-8'))
            command = [sys.executable, '-B', str(PATH), '--dependencies', str(folder)]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, '')
            self.assertEqual(result.stdout.count('normalizedIdentical True'), len(comparison.DEPENDENCY_PAIRS))
            function_lines = [line for line in result.stdout.splitlines() if line.startswith('utrie2.cpp ')][:-1]
            self.assertEqual(len({line.split()[3] for line in function_lines}), 5)
            self.assertEqual(len({line.split()[5] for line in function_lines}), 1)
            (folder / 'utrie2.cpp-70-1').write_text('missing boundary')
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertTrue(result.stderr.startswith('comparison incomplete: '))
            self.assertEqual(result.stdout.count('normalizedIdentical True'), 5)
            self.assertNotIn('utrie2.cpp', result.stdout)

    def test_dependency_slices_and_missing_boundaries(self):
        select = comparison.select_dependency
        tail = '/* Internal definitions ----------------------------------------------------- */'
        self.assertEqual(select('utrie2.h', 'prefix\n#ifdef __cplusplus\nexcluded\n' + tail + '\nmacros'),
                         'prefix\n' + tail + '\nmacros')
        start = 'U_CAPI UTrie2 * U_EXPORT2\nutrie2_openFromSerialized('
        end = 'U_CAPI UTrie2 * U_EXPORT2\nutrie2_openDummy('
        body = start + 'args) { return 0; }\n'
        self.assertEqual(select('utrie2.cpp', 'excluded\n' + body + end + 'excluded'), body)
        for source in ('', start, end, end + start, start + start + end, start + end + end):
            with self.subTest(source=source), self.assertRaises(ValueError):
                select('utrie2.cpp', source)
        for source in ('no boundary', '#ifdef __cplusplus', tail + '#ifdef __cplusplus',
                       '#ifdef __cplusplus' * 2 + tail, '#ifdef __cplusplus' + tail * 2):
            with self.subTest(source=source), self.assertRaises(ValueError):
                select('utrie2.h', source)
        self.assertEqual(select('collationdata.h', 'whole file'), 'whole file')

    def test_dependency_substitutions_are_explicit(self):
        for name, pairs in comparison.DEPENDENCY_PAIRS.items():
            for before, after in pairs:
                with self.subTest(name=name, before=before):
                    self.assertEqual(comparison.normalize(name, before, comparison.DEPENDENCY_PAIRS), after)
            self.assertNotEqual(comparison.normalize(name, 'return 1;', comparison.DEPENDENCY_PAIRS),
                                comparison.normalize(name, 'return 2;', comparison.DEPENDENCY_PAIRS))

    def test_collation_helper_slice_boundaries(self):
        markers = ('uint32_t\nCollation::incThreeBytePrimaryByOffset(',
                   'uint32_t\nCollation::decTwoBytePrimaryByOneStep(',
                   'uint32_t\nCollation::getThreeBytePrimaryForOffsetData(',
                   'U_NAMESPACE_END')
        a, b, c, d = markers
        source = 'excluded' + a + 'A' + b + 'excluded' + c + 'B' + d + 'excluded'
        self.assertEqual(comparison.select_dependency('collation.cpp', source), a + 'A' + c + 'B')
        for marker in markers:
            for invalid in (source.replace(marker, ''), source + marker):
                with self.subTest(marker=marker), self.assertRaises(ValueError):
                    comparison.select_dependency('collation.cpp', invalid)
        for invalid in (b + a + c + d, a + c + b + d, a + b + d + c):
            with self.assertRaises(ValueError):
                comparison.select_dependency('collation.cpp', invalid)

    def test_collation_cast_then_comment_spacing(self):
        source = 'uint32_t p = (uint32_t)(dataCE >> 32);  // primary'
        self.assertEqual(comparison.normalize('collation.cpp', source, comparison.DEPENDENCY_PAIRS),
                         'uint32_t p = static_cast<uint32_t>(dataCE >> 32); // primary')

    def test_dependency_report_hashes_entire_file_but_compares_slice(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for i, version in enumerate(comparison.VERSIONS):
                (folder / f'utrie2.h-{version}').write_text(
                    'prefix\n#ifdef __cplusplus\nPRIVATE' + str(i) +
                    '\n/* Internal definitions ----------------------------------------------------- */\nmacros')
            output = io.StringIO()
            with patch.object(comparison, 'DEPENDENCY_PAIRS', {'utrie2.h': []}), contextlib.redirect_stdout(output):
                comparison.compare(folder, dependencies=True)
            lines = output.getvalue().splitlines()
            self.assertEqual(len(lines), 6)
            self.assertEqual(len({line.split()[3] for line in lines[:-1]}), 5)
            self.assertEqual(len({line.split()[5] for line in lines[:-1]}), 1)
            self.assertEqual(lines[-1], 'utrie2.h normalizedIdentical True')
            self.assertNotIn('PRIVATE', output.getvalue())

    def test_word_boundaries_and_explicit_cast(self):
        source = 'NULL NULLORDER UChar UChar32 TRUE FALSE (uint32_t)ce'
        self.assertEqual(comparison.normalize('coleitr.cpp', source),
                         'nullptr NULLORDER char16_t UChar32 true false static_cast<uint32_t>(ce)')

    def test_new_flag_and_unrelated_differences_survive(self):
        source = 'CONTRACT_HAS_STARTER = 0x800; return 42;'
        self.assertEqual(comparison.normalize('collation.h', source), source)
        for name in comparison.PAIRS:
            self.assertNotEqual(comparison.normalize(name, 'return 1;'),
                                comparison.normalize(name, 'return 2;'))

    def test_literal_cast_replacement_is_not_a_cpp_parser(self):
        self.assertEqual(comparison.normalize('coleitr.cpp', '(uint32_t)ce32'),
                         'static_cast<uint32_t>(ce)32')

    def test_equal_report_at_cap_and_raw_newline_sensitivity(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for version in comparison.VERSIONS:
                (folder / f'coleitr.cpp-{version}').write_bytes(b'a\r\n')
            output = io.StringIO()
            with patch.object(comparison, 'PAIRS', {'coleitr.cpp': []}), \
                    patch.object(comparison, 'SOURCE_CAP', 3), contextlib.redirect_stdout(output):
                comparison.compare(folder)
            self.assertIn('normalizedIdentical True', output.getvalue())
            (folder / 'coleitr.cpp-70-1').write_bytes(b'a\n')
            output = io.StringIO()
            with patch.object(comparison, 'PAIRS', {'coleitr.cpp': []}), contextlib.redirect_stdout(output):
                comparison.compare(folder)
            self.assertIn('normalizedIdentical False', output.getvalue())

    def test_cli_missing_and_invalid_utf8_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for raw in (None, b'\xff'):
                with self.subTest(raw=raw):
                    if raw is not None:
                        (folder / 'collation.h-70-1').write_bytes(raw)
                    result = subprocess.run([sys.executable, '-B', str(PATH), str(folder)],
                                            capture_output=True, text=True, check=False)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, '')
                    self.assertTrue(result.stderr.startswith('comparison incomplete: '))

    def test_report_distinguishes_inequality_without_source_export(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for i, version in enumerate(comparison.VERSIONS):
                (folder / f'coleitr.cpp-{version}').write_text('PRIVATE' + str(i))
            output = io.StringIO()
            with patch.object(comparison, 'PAIRS', {'coleitr.cpp': []}), contextlib.redirect_stdout(output):
                comparison.compare(folder)
            self.assertIn('normalizedIdentical False', output.getvalue())
            self.assertNotIn('PRIVATE', output.getvalue())
            self.assertEqual(len(output.getvalue().splitlines()), 6)

    def test_cap_and_missing_file_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with self.assertRaises(OSError):
                comparison.compare(folder)
            (folder / 'collation.h-70-1').write_bytes(b'ab')
            with patch.object(comparison, 'SOURCE_CAP', 1), self.assertRaisesRegex(ValueError, 'source size cap'):
                comparison.compare(folder)


if __name__ == '__main__':
    unittest.main()
