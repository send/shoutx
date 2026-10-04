"""Synthetic checks for the research reader, not evidence of consumer safety."""
import importlib.util
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/inspect-icu-mappings.py'
spec = importlib.util.spec_from_file_location('mapping_reader', SCRIPT)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def fixture(ti=None, td=None, high=0):
    """Small root payload; no native dependency or copied vendor data."""
    ti = [0] * 2112 if ti is None else ti
    td = [0x12340505] * 192 if td is None else td
    trie = struct.pack('<I6H', 0x54726932, 1, len(ti), len(td)//4, 0, 0, high >> 11)
    trie += struct.pack(f'<{len(ti)}H', *ti)
    trie += struct.pack(f'<{len(td)}I', *td)
    trie += bytes((-len(trie)) % 8)
    indexes = [20, 0x2000, 0, 0, 0, 80, 80, 80]
    end = 80 + len(trie)
    indexes += [end, end, end + 8, end + 8]
    end += 8 + 67 * 4
    indexes += [end] * 8
    return struct.pack('<20i', *indexes) + trie + struct.pack('<Q', 0x1234000005000500) + struct.pack('<67I', *([0x12340505] * 67))


class TrieTests(unittest.TestCase):
    def entries(self, units, **kwargs):
        return dict(reader.ContextTrie(units, **kwargs).entries(0))

    def test_final_value_widths(self):
        for units, value in [([0x8007], 7), ([0xc001, 2], 0x10002), ([0xffff, 0xfedc, 0xba98], 0xfedcba98)]:
            self.assertEqual(self.entries(units), {(): value})

    def test_intermediate_widths_and_linear_match(self):
        for units, value in [([0x70], 0), ([0x4070, 9], 9), ([0x7ff0, 0x1234, 0x5678], 0x12345678)]:
            self.assertEqual(self.entries(units + [ord('x'), 0x8003]), {(): value, (ord('x'),): 3})

    def test_linear_branch(self):
        self.assertEqual(self.entries([1, 97, 0x8001, 98, 0x8002]), {(97,): 1, (98,): 2})

    def test_supplementary_key_with_intermediate_value(self):
        # Two stored UTF-16 units precede a value and a further matching unit.
        units = [0x31, 0xd83d, 0xde00, 0x70, ord('x'), 0x8007]
        self.assertEqual(self.entries(units),
                         {(0xd83d, 0xde00): 0, (0xd83d, 0xde00, ord('x')): 7})

    def test_supplementary_pair_crosses_branch_edge(self):
        # The lead-unit branch edge jumps past the last edge to a trail-unit match.
        units = [1, 0xd83d, 2, ord('x'), 0x8001, 0x30, 0xde00, 0x8007]
        self.assertEqual(self.entries(units), {(0xd83d, 0xde00): 7, (ord('x'),): 1})

    def test_multiunit_intermediate_values_before_branch(self):
        for prefix, value in [([0x4041, 9], 9), ([0x7fc1, 0x8000, 1], 0x80000001)]:
            with self.subTest(prefix=prefix):
                self.assertEqual(self.entries(prefix + [ord('a'), 0x8002, ord('b'), 0x8003]),
                                 {(): value, (ord('a'),): 2, (ord('b'),): 3})

    def test_high_bit_returned_value_is_not_a_valid_bounded_jump(self):
        self.assertEqual(self.entries([0xffff, 0x8000, 0]), {(): 0x80000000})
        # Same 32-bit pattern without the final bit is a branch jump, not a value.
        with self.assertRaisesRegex(reader.Unverified, 'reference outside section'):
            self.entries([1, ord('a'), 0x7fff, 0x8000, 0, ord('b'), 0x8001])
        # A long-branch delta uses a different lead encoding but the same bound.
        with self.assertRaisesRegex(reader.Unverified, 'reference outside section'):
            self.entries([5, 100, 0xffff, 0x8000, 0])

    def test_branch_jump(self):
        # First edge jumps over the last edge's key+value.
        self.assertEqual(self.entries([1, 97, 2, 98, 0x8002, 0x8001]), {(97,): 1, (98,): 2})

    def test_binary_branch(self):
        units = [5, 100, 6, 100, 0x8004, 101, 0x8005, 102, 0x8006,
                 97, 0x8001, 98, 0x8002, 99, 0x8003]
        self.assertEqual(self.entries(units), {(96+i,): i for i in range(1, 7)})

    def test_binary_branch_multiunit_deltas(self):
        for delta in [[0xfc00, 6], [0xffff, 0, 6]]:
            units = [5, 100] + delta + [100, 0x8004, 101, 0x8005, 102, 0x8006,
                                     97, 0x8001, 98, 0x8002, 99, 0x8003]
            self.assertEqual(self.entries(units), {(96+i,): i for i in range(1, 7)})

    def test_extended_branch_and_intermediate_branch(self):
        # ICU's decoder also permits the extended encoding for a short branch.
        self.assertEqual(self.entries([0, 1, 97, 0x8001, 98, 0x8002]), {(97,): 1, (98,): 2})
        self.assertEqual(self.entries([0x41, 97, 0x8001, 98, 0x8002]), {(): 0, (97,): 1, (98,): 2})

    def test_branch_pair_value_widths(self):
        for encoded, value in [([0xc001, 2], 0x10002), ([0xffff, 0x1234, 0x5678], 0x12345678)]:
            self.assertEqual(self.entries([1, 97] + encoded + [98, 0x8002]), {(97,): value, (98,): 2})

    def test_length_one_branch_rejected(self):
        with self.assertRaises(reader.Unverified):
            self.entries([0, 0, 97, 0x8001])

    def test_context_depth_limit(self):
        with self.assertRaisesRegex(reader.Unverified, 'context traversal bound'):
            self.entries([0x30, 97] * 130 + [0x8001], max_key=256)

    def test_delta_widths(self):
        trie = reader.ContextTrie([3, 0xfc01, 2, 0xffff, 3, 4])
        self.assertEqual(trie.delta(0), (3, 1))
        self.assertEqual(trie.delta(1), (0x10002, 3))
        self.assertEqual(trie.delta(3), (0x30004, 6))

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(reader.Unverified):
            self.entries([1, 97, 0x8001, 97, 0x8002])

    def test_truncation_and_limits(self):
        for units in [[], [0xffff], [0xffff, 1], [0x30], [1, 97], [0]]:
            with self.subTest(units=units), self.assertRaises(reader.Unverified):
                self.entries(units)
        with self.assertRaises(reader.Unverified):
            self.entries([0x8000], max_visits=0)
        with self.assertRaises(reader.Unverified):
            self.entries([0x30, 97, 0x8001], max_key=0)


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.root = reader.RootMappings(fixture())

    def test_simple_zero_and_nonzero(self):
        self.assertEqual(self.root.leading(0, 65), {False})
        self.assertEqual(self.root.leading(0x12340505, 65), {True})

    def test_real_trie_index_paths_and_high_start(self):
        ti, td = [0] * 2304, [0x12340505] * 256
        ti[2] = 8  # BMP U+0041 -> block 32, not block 0.
        td[33] = 0x22340505
        ti[0xd800 >> 5] = 16  # Lead code-unit block at data[64].
        td[64], td[65], td[66], td[68] = 0x2cd, 0x2cd, 0x2cd, 0xcd
        ti[2048] = 24  # Different lead-surrogate code-POINT index.
        td[96] = 0xc0
        ti[2112] = 2176  # First supplementary index-1 entry -> index-2 block.
        ti[2113] = 2240  # A distinct second supplementary index-1 entry.
        ti[2176], ti[2177], ti[2239] = 32, 40, 48
        ti[2240], ti[2303] = 44, 48
        td[128], td[160], td[223], td[252] = 0x33340505, 0x44340505, 0x55340505, 0xffffffff
        td[176] = 0x66340505
        root = reader.RootMappings(fixture(ti, td, high=0x11000))
        for cp, value in [(65, 0x22340505), (0x10000, 0x33340505), (0x10020, 0x44340505),
                          (0x107ff, 0x55340505), (0x10800, 0x66340505), (0x10fff, 0x55340505),
                          (0x11000, 0xffffffff), (0x10ffff, 0xffffffff)]:
            self.assertEqual(root.lookup(cp), value)
        self.assertEqual(root.lookup(0xd800, lead_unit=True), 0x2cd)
        self.assertEqual(root.initial(0x10000), 0x33340505)
        self.assertEqual(root.initial(0x107ff), 0x55340505)
        self.assertEqual(root.initial(0x10800), 0x66340505)
        self.assertEqual(root.initial(0x11000), 0xffffffff)
        with self.assertRaises(reader.Unverified):
            root.lookup(0xd800)

    def test_trie_padding(self):
        root = reader.RootMappings(fixture(ti=[0]*2114))
        self.assertEqual(root.lookup(65), 0x12340505)

    def test_split_first_half_not_whole_ce(self):
        self.assertEqual(reader.first_half(1), 0)
        self.root.ces = (1, 0x1234000005000500)
        self.assertEqual(self.root.leading((2 << 8) | 0xc6, 65), {False})

    def test_direct_and_latin(self):
        for value in [0x123400c1, 0x050005c2, 0x120505c4]:
            self.assertEqual(self.root.leading(value, 65), {True})

    def test_expansion32_all_entries_validated(self):
        self.root.ce32s = (0, 0x12340505)
        self.assertEqual(self.root.leading(0x2c5, 65), {False})
        self.root.ce32s = (0x12340505, 0xc9)
        with self.assertRaises(reader.Unverified):
            self.root.leading(0x2c5, 66)

    def test_expansion_bounds(self):
        for value in [0xc5, (1000 << 13) | 0x1c5, 0xc6, (1000 << 13) | 0x1c6]:
            with self.subTest(value=value), self.assertRaises(reader.Unverified):
                self.root.leading(value, 65)

    def test_end_sentinel_in_expansion(self):
        self.root.ces = (0x101000100,)
        with self.assertRaises(reader.Unverified):
            self.root.leading(0x1c6, 65)

    def test_default_and_context_alternatives(self):
        self.root.contexts = (0, 0, 0x30, 97, 0xd234, 0x0505)
        for value in [0xc8, 0xc9]:
            self.assertEqual(self.root.leading(value, 65), {False, True})
        self.assertEqual(len(self.root.context_cache), 1)

    def test_contraction_scalar_dependent_alternative_unverified(self):
        self.root.contexts = (0, 0, 0x30, 97, 0x80ce)
        with self.assertRaises(reader.Unverified):
            self.root.leading(0xc9, 65)

    def test_prefix_preserves_scalar(self):
        self.root.contexts = (0, 0, 0x30, 97, 0x80ce)
        self.assertEqual(self.root.leading(0xc8, 65), {False, True})

    def test_nested_prefix_contraction(self):
        self.root.contexts = (0x1234, 0x0505, 0x30, 97, 0xc001, 0x00c9, 0, 0,
                              0, 0, 0x30, 98, 0xd234, 0x0505)
        self.assertEqual(self.root.leading(0xc8, 65), {False, True})
        self.assertEqual(len(self.root.context_cache), 2)

    def test_digit_and_cycle(self):
        self.root.ce32s = (0x12340505,)
        self.assertEqual(self.root.leading(0xca, 48), {True})
        self.root.ce32s = (0xca,)
        with self.assertRaises(reader.Unverified):
            self.root.leading(0xca, 49)

    def test_context_cycle(self):
        self.root.contexts = (0, 0xc8, 0x30, 97, 0x8000)
        with self.assertRaises(reader.Unverified):
            self.root.leading(0xc8, 65)

    def test_hangul_first_jamo_only_but_all_validated(self):
        self.assertEqual(self.root.leading(0x1cc, 0xac00), {True})
        self.root.jamo = tuple([0] + [0x12340505] * 66)
        self.assertEqual(self.root.leading(0xcc, 0xac01), {False})
        self.root.jamo = tuple([0x12340505] * 19 + [0xc7] + [0x12340505] * 47)
        with self.assertRaises(reader.Unverified):
            self.root.leading(0xcc, 0xac02)

    def test_algorithmic_requires_scalar(self):
        for value in [0xce, 0xffffffff]:
            self.assertEqual(self.root.leading(value, 65), {True})
            with self.assertRaises(reader.Unverified):
                self.root.leading(value, -1)

    def test_unsupported_does_not_pass(self):
        for value in [1, 0xc0, 0xc3, 0xc7, 0xcb, 0xcd, 0xcf]:
            with self.subTest(value=value), self.assertRaises(reader.Unverified):
                self.root.leading(value, 65)

    def test_lead_unit_summary(self):
        original = self.root.lookup
        self.root.lookup = lambda cp, lead_unit=False: 0xcd if lead_unit else 0xffffffff
        self.assertEqual(self.root.initial(0x10000), 0xffffffff)
        self.root.lookup = lambda cp, lead_unit=False: 0xcd if lead_unit else 0x12340505
        with self.assertRaises(reader.Unverified):
            self.root.initial(0x10000)
        self.root.lookup = lambda cp, lead_unit=False: 0x1cd if lead_unit else 0xc0
        with self.assertRaises(reader.Unverified):
            self.root.initial(0x10000)
        self.root.lookup = lambda cp, lead_unit=False: 0x2cd if lead_unit else 0x12340505
        self.assertEqual(self.root.initial(0x10000), 0x12340505)
        self.root.lookup = lambda cp, lead_unit=False: 0x3cd if lead_unit else 0x12340505
        self.assertEqual(self.root.initial(0x10000), 0x12340505)
        for invalid in [0x4cd, 0xcc]:
            self.root.lookup = lambda cp, lead_unit=False: invalid if lead_unit else 0x12340505
            with self.assertRaises(reader.Unverified):
                self.root.initial(0x10000)
        self.root.lookup = original

    def test_resource_bound(self):
        self.root.mapping_visits = 500000
        with self.assertRaises(reader.Unverified):
            self.root.leading(0, 65)

    def test_context_global_bounds(self):
        self.root.context_cache = {i: (0, []) for i in range(4096)}
        with self.assertRaisesRegex(reader.Unverified, 'context count bound'):
            self.root.context_values(4096)
        self.root.context_cache = {}
        self.root.context_entry_count = 100000
        self.root.contexts = (0, 0, 0x30, 97, 0x8001)
        with self.assertRaisesRegex(reader.Unverified, 'total context entry bound'):
            self.root.context_values(0)

    def test_mapping_depth_limit(self):
        self.root.ce32s = tuple(((i+1) << 13) | 0xca for i in range(65))
        with self.assertRaisesRegex(reader.Unverified, 'mapping cycle/depth'):
            self.root.leading(0xca, 48)

    def test_bad_constructor_fields(self):
        for offset, code, value in [(80, 'I', 0), (84, 'H', 0), (94, 'H', 545),
                                     (28, 'i', 81), (16, 'i', -1)]:
            raw = bytearray(fixture())
            struct.pack_into('<'+code, raw, offset, value)
            with self.subTest(offset=offset), self.assertRaises(reader.Unverified):
                reader.RootMappings(raw)

    def test_bad_payload_and_numeric_setting(self):
        for raw in [b'', fixture()[:70], fixture() + b'x' * 16]:
            with self.subTest(length=len(raw)), self.assertRaises(reader.Unverified):
                reader.RootMappings(raw)
        raw = bytearray(fixture())
        struct.pack_into('<i', raw, 4, 0x2002)
        with self.assertRaises(reader.Unverified):
            reader.RootMappings(raw)

    def test_output_is_not_acceptance_evidence(self):
        result = reader.inspect(fixture(), [65])
        self.assertFalse(result['acceptanceTable'])
        self.assertFalse(result['offsetsProven'])
        self.assertFalse(result['consumerIdentityProven'])
        self.assertEqual(result['candidateCount'], 1)

    def test_cli_hash_failure_empty_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path/'root').write_bytes(fixture())
            (path/'candidates').write_text(json.dumps({'ranges': [[65, 65]]}))
            result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--root-data', str(path/'root'),
                '--sha256', '0'*64, '--candidates', str(path/'candidates')], capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b'')
            self.assertIn(b'payload hash mismatch', result.stderr)

    def test_cli_usage_failure_exit_one(self):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT)], capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b'')
        self.assertIn(b'unverified:', result.stderr)

    def test_cli_unsupported_mapping_exit_two(self):
        raw = bytearray(fixture())
        struct.pack_into('<I', raw, 80 + 16 + 2112 * 2 + 4, 0xc7)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path/'root').write_bytes(raw)
            (path/'candidates').write_text(json.dumps({'ranges': [[65, 65]]}))
            result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--root-data', str(path/'root'),
                '--sha256', hashlib.sha256(raw).hexdigest(), '--candidates', str(path/'candidates')], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stderr, b'')
            report = json.loads(result.stdout)
            self.assertEqual(report['classification'], {'unverified': 1})
            self.assertFalse(report['acceptanceTable'])

    def test_cli_success_and_bad_candidate_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            raw = fixture()
            (path/'root').write_bytes(raw)
            command = [sys.executable, '-B', str(SCRIPT), '--root-data', str(path/'root'),
                       '--sha256', hashlib.sha256(raw).hexdigest(), '--candidates', str(path/'candidates')]
            (path/'candidates').write_text(json.dumps({'ranges': [[65, 65]]}))
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(json.loads(result.stdout)['inputProfileVerified'])
            for candidate_text in ['{', '{"ranges": [[55296, 55296]]}', '{"ranges": [[true, 65]]}']:
                (path/'candidates').write_text(candidate_text)
                result = subprocess.run(command, capture_output=True)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, b'')
            (path/'candidates').unlink()
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b'')


if __name__ == '__main__':
    unittest.main()
