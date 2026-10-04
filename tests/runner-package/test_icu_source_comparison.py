import contextlib
import importlib.util
import io
from pathlib import Path
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
