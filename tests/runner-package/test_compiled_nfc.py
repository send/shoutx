import hashlib
import importlib.util
import json
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[2] / 'scripts/inspect-compiled-nfc.py'
spec = importlib.util.spec_from_file_location('compiled_nfc', PATH)
nfc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nfc)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fixture(version=4, wrapped=False):
    count = {4: 20, 5: 22}[version]
    lines = [f'static const UVersionInfo norm2_nfc_data_formatVersion={{{version},0,0,0}};']
    values_by_name = {'indexes': list(range(100, 100 + count)),
                      'trieIndex': [201, 202, 203], 'trieData': [301, 302, 303, 304],
                      'extraData': [401, 402, 403, 404, 405], 'smallFCD': [11, 12, 13]}
    for name, (kind, _) in nfc.ARRAY_TYPES.items():
        length = 'Normalizer2Impl::IX_COUNT' if name == 'indexes' else str(len(values_by_name[name]))
        separator = ',\n' if wrapped else ','
        values = separator.join(hex(i) if wrapped else str(i) for i in values_by_name[name])
        lines.append(f'static const {kind} norm2_nfc_data_{name}[{length}]={{\n{values}\n}};')
        if wrapped:
            lines.append('// unrelated generated-header content')
    if wrapped:
        lines.insert(1, 'static const UVersionInfo norm2_nfc_data_dataVersion={0x10,0,0,0};')
        lines.insert(3, 'static const UCPTrie norm2_nfc_data_trie={\n0, {0}, 0\n};')
        lines = ['#ifdef INCLUDED_FROM_NORMALIZER2_CPP'] + lines + ['#endif']
    return '\n'.join(lines).encode()


class CompiledNfcTests(unittest.TestCase):
    def test_both_formats_and_explicit_little_endian(self):
        for version, count in [(4, 20), (5, 22)]:
            with self.subTest(version=version):
                major, arrays = nfc.arrays(fixture(version))
                self.assertEqual(major, version)
                self.assertEqual(len(arrays['indexes']), count * 4)
                self.assertEqual(arrays['indexes'][:4], b'd\0\0\0')
                self.assertEqual(arrays['trieData'][:2], b'\x2d\x01')
                self.assertEqual(arrays['smallFCD'], b'\x0b\x0c\x0d')
                self.assertEqual(nfc.arrays(fixture(version, wrapped=True)), (major, arrays))

    def test_rejects_declaration_and_numeric_changes(self):
        raw = fixture()
        variants = [raw.replace(b'{4,0,0,0}', b'{6,0,0,0}'),
                    raw.replace(b'IX_COUNT', b'OTHER'),
                    raw.replace(b'trieData[4]', b'trieData[5]'),
                    raw.replace(b'trieData[4]', b'trieData[65537]'),
                    raw.replace(b'trieData[4]', b'trieData[0]'),
                    raw.replace(b'trieData[4]', b'trieData[1+2]'),
                    raw.replace(b'100,101,102', b'100,101,102,'),
                    raw.replace(b'100,101,102', b'100,-1,102'),
                    raw.replace(b'100,101,102', b'100,1<<2,102'),
                    raw.replace(b'100,101,102', b'100,/*x*/101,102'),
                    raw.replace(b'100,101,102', b'100,0101,102'),
                    raw.replace(b'100,101,102', b'100,999999999999,102'),
                    raw.replace(b'uint16_t norm2_nfc_data_trieIndex',
                                b'uint8_t norm2_nfc_data_trieIndex'),
                    raw.replace(b'norm2_nfc_data_trieIndex', b'norm2_nfc_data_unexpected'),
                    raw + b'\n' + raw,
                    raw[:raw.index(b'static const uint8_t')], b'\xff']
        for value in variants:
            with self.subTest(value=value[:100]), self.assertRaises(ValueError):
                nfc.arrays(value)

    def test_format_count_mismatch(self):
        with self.assertRaises(ValueError):
            nfc.arrays(fixture().replace(b'{4,0,0,0}', b'{5,0,0,0}'))
        with self.assertRaises(ValueError):
            nfc.arrays(fixture(5).replace(b'{5,0,0,0}', b'{4,0,0,0}'))

    def files(self, folder, source=None, binary=None):
        source = fixture() if source is None else source
        if binary is None:
            binary = b'PRIVATE PREFIX' + b''.join(nfc.arrays(source)[1].values()) + b'PRIVATE SUFFIX'
        a, b = Path(folder) / 'source.h', Path(folder) / 'binary'
        a.write_bytes(source)
        b.write_bytes(binary)
        return a, b, digest(source), digest(binary)

    def test_report_offsets_and_no_data_export(self):
        with tempfile.TemporaryDirectory() as folder:
            args = self.files(folder)
            report = nfc.inspect(*args)
            self.assertTrue(report['allArraysLocated'])
            self.assertEqual(report['arrays']['indexes']['firstFileOffsets'], [14])
            location = 14
            for name, payload in nfc.arrays(fixture())[1].items():
                self.assertEqual(report['arrays'][name]['firstFileOffsets'], [location])
                self.assertEqual(report['arrays'][name]['occurrencesInRegion'], 1)
                location += len(payload)
            self.assertFalse(report['nativeUseProven'])
            self.assertFalse(report['normalizationProfileProven'])
            self.assertNotIn('PRIVATE', json.dumps(report))
            self.assertNotIn('payload', json.dumps(report))

    def test_region_and_missing_arrays_are_observations(self):
        with tempfile.TemporaryDirectory() as folder:
            args = self.files(folder)
            report = nfc.inspect(*args, offset=14, size=80)
            self.assertEqual(report['regionOffset'], 14)
            self.assertEqual(report['arrays']['indexes']['firstFileOffsets'], [14])
            self.assertEqual(report['arrays']['smallFCD']['occurrencesInRegion'], 0)
            self.assertFalse(report['allArraysLocated'])

    def test_overlapping_matches_bounded_offsets(self):
        source = fixture().replace(b'11,12,13', b'0,0,0')
        with tempfile.TemporaryDirectory() as folder:
            report = nfc.inspect(*self.files(folder, source, bytes(100)))
            self.assertEqual(report['arrays']['smallFCD']['occurrencesInRegion'], 98)
            self.assertEqual(report['arrays']['smallFCD']['firstFileOffsets'], list(range(8)))
            with patch.object(nfc, 'MATCH_CAP', 97), self.assertRaisesRegex(ValueError, 'occurrence cap'):
                nfc.inspect(*self.files(folder, source, bytes(100)))

    def test_hashes_cover_outside_region(self):
        with tempfile.TemporaryDirectory() as folder:
            args = self.files(folder)
            original = args[1].read_bytes()
            for changed in [b'!' + original[1:], original[:-1] + b'!']:
                args[1].write_bytes(changed)
                with self.assertRaisesRegex(ValueError, 'binary identity mismatch'):
                    nfc.inspect(*args, offset=14, size=80)

    def test_multichunk_regions_and_array_crossing_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            args = self.files(folder, fixture(5, wrapped=True))
            baseline = nfc.inspect(*args, offset=14, size=88)
            whole_file = nfc.inspect(*args)
            for chunk in [1, 7, 16, 31, 64]:
                with self.subTest(chunk=chunk), patch.object(nfc, 'CHUNK_SIZE', chunk):
                    self.assertEqual(nfc.inspect(*args, offset=14, size=88), baseline)
                    self.assertEqual(nfc.inspect(*args), whole_file)

    def test_size_change_and_growth_cap(self):
        with tempfile.TemporaryDirectory() as folder:
            args = self.files(folder)
            binary = args[1].read_bytes()
            original_open = nfc.open_regular

            class ChangedStream(io.BytesIO):
                def __init__(self, data, descriptor):
                    super().__init__(data)
                    self.descriptor = descriptor

                def fileno(self):
                    return self.descriptor

            with args[1].open('rb') as actual:
                def opened(path):
                    return ChangedStream(changed, actual.fileno()) if path == args[1] else original_open(path)
                for changed in [binary[:-1], binary + b'X']:
                    with patch.object(nfc, 'open_regular', opened), \
                            self.assertRaisesRegex(ValueError, 'size changed or short region'):
                        nfc.inspect(*args)
                changed = binary + b'X'
                with patch.object(nfc, 'open_regular', opened), \
                        patch.object(nfc, 'BINARY_CAP', len(binary)), \
                        self.assertRaisesRegex(ValueError, 'binary size cap'):
                    nfc.inspect(*args)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'Unix FIFO control')
    def test_fifo_rejected_without_waiting_for_writer(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pipe'
            os.mkfifo(path)
            cmd = [sys.executable, '-B', str(PATH), str(path), str(path),
                   '--source-sha256', '0' * 64, '--binary-sha256', '0' * 64]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=5)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, '')
            self.assertIn('regular file', result.stderr)
            source, _, source_hash, _ = self.files(folder)
            cmd[3], cmd[6] = str(source), source_hash
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=5)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, '')
            self.assertIn('regular file', result.stderr)

    def test_invalid_regions_and_caps(self):
        with tempfile.TemporaryDirectory() as folder:
            args = self.files(folder)
            for offset, size in [(-1, 1), (0, 0), (0, -1), (100000, 1), (0, 100000),
                                 (True, 1), (0, True), (0.0, 1)]:
                with self.subTest(offset=offset, size=size), self.assertRaises(ValueError):
                    nfc.inspect(*args, offset=offset, size=size)
            for constant, cap in [('SOURCE_CAP', len(args[0].read_bytes()) - 1),
                                  ('BINARY_CAP', args[1].stat().st_size - 1), ('REGION_CAP', 79)]:
                with self.subTest(constant=constant), patch.object(nfc, constant, cap), \
                        self.assertRaises(ValueError):
                    nfc.inspect(*args, offset=14, size=80)
            with patch.object(nfc, 'SOURCE_CAP', len(args[0].read_bytes())), \
                    patch.object(nfc, 'BINARY_CAP', args[1].stat().st_size), \
                    patch.object(nfc, 'REGION_CAP', 80):
                self.assertEqual(nfc.inspect(*args, offset=14, size=80)['regionBytes'], 80)

    def test_cli_success_and_failures_have_no_partial_stdout(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b, sa, sb = self.files(folder)
            cmd = [sys.executable, '-B', str(PATH), str(a), str(b),
                   '--source-sha256', sa, '--binary-sha256', sb]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['allArraysLocated'])
            self.assertEqual(result.stderr, '')
            result = subprocess.run(cmd + ['--size', '1'], capture_output=True,
                                    text=True, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(json.loads(result.stdout)['allArraysLocated'])
            for extra in [['--offset', '-1'], ['--size', '0'], ['--size', '100000']]:
                result = subprocess.run(cmd + extra, capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, '')
            for source_hash, binary_hash in [('0' * 64, sb), (sa, '0' * 64), ('invalid', sb)]:
                bad = cmd[:6] + [source_hash, '--binary-sha256', binary_hash]
                result = subprocess.run(bad, capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, '')
                self.assertTrue(result.stderr.startswith('inspection incomplete: '))
            for content in [b'\xff', fixture().replace(b'{4,0,0,0}', b'{99,0,0,0}')]:
                a.write_bytes(content)
                bad = cmd[:6] + [digest(content), '--binary-sha256', sb]
                result = subprocess.run(bad, capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, '')
            a.unlink()
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
