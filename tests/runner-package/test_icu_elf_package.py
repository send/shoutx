import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import icu_elf_package as probe
from test_icu_package_inventory import fixture as package_fixture


def fixture():
    package = package_fixture().replace(b'icudt72l', b'icudt70l')
    raw = bytearray(256) + package
    raw[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HHI', raw, 16, 3, 62, 1)
    struct.pack_into('<Q', raw, 32, 64)
    struct.pack_into('<HHH', raw, 52, 64, 56, 1)
    struct.pack_into('<IIQQQQQQ', raw, 64, 1, 4, 256, 0x2000, 0,
                     len(package), len(package), 1)
    return raw, len(package)


def inspect(raw, size):
    return probe.inspect(raw, hashlib.sha256(raw).hexdigest(), 0x2000, size, 'icudt70l')


class ElfTests(unittest.TestCase):
    def test_valid_mapping_not_va_equal_file_offset(self):
        raw, size = fixture()
        result = inspect(raw, size)
        self.assertEqual(result['symbolFileOffset'], 256)
        self.assertEqual(result['suppliedSymbolVA'], 8192)
        self.assertEqual(result['package']['entryCount'], 3)
        self.assertEqual(result['package']['members']['coll/en.res']['offset'], 256)
        self.assertNotIn('raw', result)

    def test_hash_checked_before_parsing(self):
        with self.assertRaisesRegex(ValueError, '^file-hash-mismatch$'):
            probe.inspect(b'not ELF', '0' * 64, 0, 1, 'icudt70l')

    def test_headers_and_load_bounds(self):
        for offset, fmt, value in [(4, 'B', 1), (5, 'B', 2), (6, 'B', 0),
                                   (16, 'H', 2), (18, 'H', 183), (20, 'I', 0),
                                   (32, 'Q', 0), (52, 'H', 63), (54, 'H', 55),
                                   (56, 'H', 0), (56, 'H', 1025), (64, 'I', 0),
                                   (72, 'Q', 2**64-1), (96, 'Q', 2**64-1),
                                   (104, 'Q', 1)]:
            raw, size = fixture()
            struct.pack_into('<' + fmt, raw, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                inspect(raw, size)

    def test_truncated_zero_fill_and_ambiguous_mapping(self):
        raw, size = fixture()
        for short in (b'', raw[:63], raw[:110], raw[:-1]):
            with self.assertRaises(ValueError):
                inspect(short, size)
        struct.pack_into('<Q', raw, 96, size - 1)
        with self.assertRaisesRegex(ValueError, '^symbol-file-mapping$'):
            inspect(raw, size)
        raw, size = fixture()
        struct.pack_into('<H', raw, 56, 2)
        raw[120:176] = raw[64:120]
        with self.assertRaisesRegex(ValueError, '^symbol-file-mapping$'):
            inspect(raw, size)

    def test_resource_cap_and_invalid_symbol_span(self):
        raw, size = fixture()
        with patch.object(probe, 'FILE_CAP', len(raw)):
            inspect(raw, size)
        with patch.object(probe, 'FILE_CAP', len(raw) - 1), self.assertRaises(ValueError):
            inspect(raw, size)
        for address, length in [(-1, size), (0x2000, 0), (2**64-1, 2)]:
            with self.assertRaises(ValueError):
                probe.mapped_span(raw, address, length)

    def test_reuses_complete_toc_validation(self):
        raw, size = fixture()
        struct.pack_into('<I', raw, 256 + 168, 0)  # unselected final entry
        with self.assertRaisesRegex(ValueError, '^unsupported-package-layout$'):
            inspect(raw, size)

    def test_cli_failure_empty_stdout_including_optimized_python(self):
        script = str(Path(probe.__file__).resolve())
        raw, size = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.elf'
            path.write_bytes(raw)
            for flags in ([], ['-O']):
                for extra in (['--sha256', '0' * 64], ['--sha256', 'bad']):
                    result = subprocess.run([sys.executable, *flags, '-B', script, str(path),
                                             '--symbol-va', '0x2000', '--symbol-size', str(size),
                                             '--prefix', 'icudt70l', *extra], capture_output=True)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, b'')
                    self.assertTrue(result.stderr.startswith(b'unverified: '))

    def test_cli_success_and_malformed_matching_file(self):
        raw, size = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.elf'
            command = [sys.executable, '-B', str(Path(probe.__file__).resolve()), str(path),
                       '--symbol-va', '0x2000', '--symbol-size', str(size), '--prefix', 'icudt70l']
            for valid in (True, False):
                if not valid:
                    raw[4] = 1
                path.write_bytes(raw)
                result = subprocess.run(command + ['--sha256', hashlib.sha256(raw).hexdigest()],
                                        capture_output=True)
                if valid:
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stderr, b'')
                    self.assertEqual(json.loads(result.stdout)['symbolFileOffset'], 256)
                else:
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, b'')
                    self.assertEqual(result.stderr, b'unverified: elf-format\n')

    def test_cli_missing_file_and_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            command = [sys.executable, '-B', str(Path(probe.__file__).resolve())]
            for arguments, reason in [([], b'invalid arguments'),
                                      ([str(Path(directory) / 'missing'), '--sha256', '0' * 64,
                                        '--symbol-va', '0x2000', '--symbol-size', '496',
                                        '--prefix', 'icudt70l'], b'file-read-error')]:
                result = subprocess.run(command + arguments, capture_output=True)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, b'')
                self.assertEqual(result.stderr, b'unverified: ' + reason + b'\n')


if __name__ == '__main__':
    unittest.main()
