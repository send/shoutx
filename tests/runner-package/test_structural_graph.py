"""Synthetic graph tests; not native consumer or termination attestation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_mapping_inventory import fixture

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/inspect-icu-graph.py'
spec = importlib.util.spec_from_file_location('structural_graph', SCRIPT)
graph = importlib.util.module_from_spec(spec)
spec.loader.exec_module(graph)
SIMPLE = 0x12340505


def valid_fixture(lead=0x2cd, *, colon=SIMPLE, context_key=None):
    ti, td = [0] * 2112, [SIMPLE] * 192
    for i in range(0xd800 >> 5, 0xdc00 >> 5):
        ti[i] = 8
    td[32:64] = [lead] * 32
    td[0x3a & 31] = colon
    if context_key is not None:
        # A and B use a separate data block and share one serialized trie.
        ti[65 >> 5] = 16
        td[64 + (65 & 31)] = 0xc9  # contraction
        td[64 + (66 & 31)] = 0xc8  # prefix
    raw = bytearray(fixture(ti=ti, td=td))
    if context_key is not None:
        contexts = (SIMPLE >> 16, SIMPLE & 0xffff, 0x30, context_key,
                    0xffff, SIMPLE >> 16, SIMPLE & 0xffff)
        raw.extend(struct.pack('<7H', *contexts))
        # Context section starts at index 13; all later sections are empty.
        for index in range(14, 20):
            struct.pack_into('<i', raw, index * 4, len(raw))
    return bytes(raw)


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.root = graph.reader.RootMappings(fixture())
        self.g = graph.StructuralGraph(self.root)

    def test_terminal_kinds(self):
        for value in (0, SIMPLE, 0x123400c1, 0x050005c2, 0x120505c4,
                      0xffffffff, 0xce, 0x1c5, 0x1c6):
            with self.subTest(value=value):
                self.assertEqual(self.g.rank(value, 65), 0)

    def test_delimiter_simple_mapping(self):
        evidence = graph.delimiter_mapping_evidence(self.root)
        self.assertEqual(evidence['colonCE32'], '12340505')
        self.assertEqual(evidence['colonFirstRawHalf'], SIMPLE)
        self.assertEqual(evidence['colonSecondRawHalf'], 0)
        self.assertTrue(evidence['colonSingleNonzeroRawHalf'])
        self.assertFalse(evidence['delimiterEntryStateProven'])

    def test_delimiter_zero_is_not_positive(self):
        self.root.initial = lambda cp: 0
        evidence = graph.delimiter_mapping_evidence(self.root)
        self.assertTrue(evidence['colonSimpleMapping'])
        self.assertEqual(evidence['colonFirstRawHalf'], 0)
        self.assertFalse(evidence['colonSingleNonzeroRawHalf'])

    def test_delimiter_special_mappings_not_inferred(self):
        for value in (1, 0x123400c1, 0x050005c2, 0xc8, 0xc9, 0x1c5):
            self.root.initial = lambda cp: value
            with self.subTest(value=value):
                evidence = graph.delimiter_mapping_evidence(self.root)
                self.assertFalse(evidence['colonSimpleMapping'])
                self.assertIsNone(evidence['colonFirstRawHalf'])
                self.assertIsNone(evidence['colonSecondRawHalf'])
                self.assertFalse(evidence['colonSingleNonzeroRawHalf'])

    def test_delimiter_simple_tag_boundary(self):
        for value, simple in ((0x123405bf, True), (0x123405c0, False)):
            with self.subTest(value=value):
                self.root.initial = lambda cp: value
                evidence = graph.delimiter_mapping_evidence(self.root)
                self.assertEqual(evidence['colonSimpleMapping'], simple)
                self.assertEqual(evidence['colonFirstRawHalf'], value if simple else None)
                self.assertEqual(evidence['colonSecondRawHalf'], 0 if simple else None)

    def test_inspect_populated_contexts(self):
        for key in (58, 97):
            with self.subTest(key=key):
                result = graph.inspect(valid_fixture(context_key=key))
                self.assertTrue(result['allNonNulScalarRootsCompleted'])
                self.assertTrue(result['structuralGraphAcyclic'])
                self.assertEqual(result['rootCountCompleted'], 1112063)
                self.assertEqual(result['contextTries'], 1)
                evidence = result['delimiterMappingEvidence']
                self.assertEqual(evidence['contextEntriesExamined'], 1)
                self.assertEqual(evidence['contextKeysContainingColon'], int(key == 58))
                self.assertEqual(evidence['colonAbsentFromContextKeys'], key != 58)
                self.assertFalse(evidence['delimiterEntryStateProven'])

    def test_delimiter_context_keys_any_position(self):
        # Both reversed prefix keys and forward contraction keys are counted;
        # this property is independent of their direction or selected value.
        self.root.context_cache = {
            0: (SIMPLE, [((58, 97), SIMPLE), ((97, 58), 0)]),
            9: (SIMPLE, [((97, 58, 98), SIMPLE), ((58, 58), SIMPLE),
                         ((), SIMPLE), ((97,), SIMPLE)])}
        evidence = graph.delimiter_mapping_evidence(self.root)
        self.assertEqual(evidence['contextEntriesExamined'], 6)
        self.assertEqual(evidence['contextKeysContainingColon'], 4)
        self.assertFalse(evidence['colonAbsentFromContextKeys'])
        self.assertFalse(evidence['delimiterEntryStateProven'])

    def test_delimiter_context_values_are_not_keys(self):
        self.root.context_cache = {0: (58, [((0xd83d, 0xde00), 58)])}
        evidence = graph.delimiter_mapping_evidence(self.root)
        self.assertEqual(evidence['contextEntriesExamined'], 1)
        self.assertEqual(evidence['contextKeysContainingColon'], 0)
        self.assertTrue(evidence['colonAbsentFromContextKeys'])

    def test_delimiter_uses_contexts_discovered_by_graph(self):
        self.root.contexts = (SIMPLE >> 16, SIMPLE & 0xffff, 0x30, 58,
                              0xffff, SIMPLE >> 16, SIMPLE & 0xffff)
        self.assertFalse(self.root.context_cache)
        self.g.rank(0xc9, 65)
        self.g.rank(0xc8, 66)  # Same stored trie, count its entry only once.
        evidence = graph.delimiter_mapping_evidence(self.root)
        self.assertEqual(evidence['contextEntriesExamined'], 1)
        self.assertEqual(evidence['contextKeysContainingColon'], 1)
        self.assertFalse(evidence['colonAbsentFromContextKeys'])

    def test_rejected_tags_and_sentinel(self):
        for value in (1, 0xc0, 0x100c0, 0xc3, 0xc7, 0xcb, 0xcd):
            with self.subTest(value=value), self.assertRaises(graph.reader.Unverified):
                self.g.rank(value, 65)
        for value in (0xcc, 0xce, 0xffffffff):
            with self.subTest(value=value), self.assertRaises(graph.reader.Unverified):
                self.g.rank(value, -1)

    def test_argument_validation(self):
        for cp in (0, -2, 0xd800, 0x110000):
            with self.assertRaises(graph.reader.Unverified):
                self.g.rank(SIMPLE, cp)

    def test_direct_expansion_all_entries(self):
        for invalid in (1, 0xc8, 0xc0):
            self.root.ce32s = (SIMPLE, invalid)
            with self.assertRaises(graph.reader.Unverified):
                self.g.rank(0x2c5, 65)
        self.assertFalse(self.g.active)

    def test_expansion_bounds_and_end_sentinel(self):
        for value in (0xc5, 0xc6, (100 << 13) | 0x1c6):
            with self.assertRaises(graph.reader.Unverified):
                self.g.rank(value, 65)
        self.root.ces = (0x101000100,)
        with self.assertRaises(graph.reader.Unverified):
            self.g.rank(0x1c6, 65)

    def test_digit_rank_and_invalid_digit(self):
        self.root.ce32s = (SIMPLE, 0xca)
        self.assertEqual(self.g.rank((1 << 13) | 0xca, 65), 2)
        with self.assertRaises(graph.reader.Unverified):
            self.g.rank(0xaca, 65)

    def test_cycle_is_not_budget(self):
        self.root.ce32s = (0xca,)
        with self.assertRaises(graph.GraphFailure) as caught:
            self.g.rank(0xca, 65)
        self.assertEqual(caught.exception.kind, 'cycle')
        self.assertFalse(self.g.ranks)
        self.assertFalse(self.g.active)

    def test_two_node_cycle(self):
        self.root.ce32s = ((1 << 13) | 0xca, 0xca)
        with self.assertRaisesRegex(graph.GraphFailure, 'cycle'):
            self.g.rank(0xca, 65)

    def test_limits_never_cached_as_success(self):
        for kwargs in ({'max_nodes': 0}, {'max_depth': 0}):
            g = graph.StructuralGraph(self.root, **kwargs)
            with self.assertRaises(graph.GraphFailure) as caught:
                g.rank(SIMPLE, 65)
            self.assertEqual(caught.exception.kind, 'budget')
            self.assertFalse(g.ranks)

    def test_shared_child_is_not_cycle(self):
        self.root.context_values = lambda _: (SIMPLE, SIMPLE)
        self.assertEqual(self.g.rank(0xc8, 65), 1)
        self.assertEqual(len(self.g.ranks), 2)

    def test_nonzero_depth_bound_mid_chain(self):
        self.root.ce32s = ((1 << 13) | 0xca, SIMPLE)
        g = graph.StructuralGraph(self.root, max_depth=2)
        with self.assertRaises(graph.GraphFailure) as caught:
            g.rank(0xca, 65)
        self.assertEqual(caught.exception.kind, 'budget')
        self.assertEqual(g.nodes_started, 2)
        self.assertEqual(g.ranks, {})
        self.assertFalse(g.active)

    def test_node_bound_after_cached_node(self):
        g = graph.StructuralGraph(self.root, max_nodes=2)
        self.assertEqual(g.rank(SIMPLE, 65), 0)
        self.assertEqual(g.rank(SIMPLE, 65), 0)
        with self.assertRaises(graph.GraphFailure) as caught:
            g.rank(0xca, 66)
        self.assertEqual(caught.exception.kind, 'budget')
        self.assertEqual(g.nodes_started, 2)
        self.assertEqual(g.ranks, {(SIMPLE, 65): 0})
        self.assertFalse(g.active)

    def test_inspect_graph_budget_report(self):
        cls = graph.StructuralGraph
        with patch.object(graph, 'StructuralGraph', side_effect=lambda root: cls(root, max_nodes=1)):
            result = graph.inspect(valid_fixture())
        self.assertEqual(result['failure']['kind'], 'budget')
        self.assertEqual(result['failure']['rootScalar'], 2)
        self.assertEqual(result['rootCountCompleted'], 1)
        self.assertIsNone(result['structuralGraphAcyclic'])

    def test_decoder_budget_distinguished_from_bad_reference(self):
        self.root.contexts = (SIMPLE >> 16, SIMPLE & 0xffff, 0x8000)
        self.root.lookup = lambda cp, lead_unit=False: 0xc8
        trie_cls = graph.reader.ContextTrie
        with patch.object(graph.reader, 'RootMappings', return_value=self.root):
            with patch.object(graph.reader, 'ContextTrie',
                              side_effect=lambda units: trie_cls(units, max_visits=0)):
                result = graph.inspect(b'')
            self.assertEqual(result['failure']['kind'], 'decoder_budget')
            self.assertEqual(result['failure']['reason'], 'context traversal bound')
            self.assertIsNone(result['structuralGraphAcyclic'])
            self.root.contexts = ()
            result = graph.inspect(b'')
            self.assertEqual(result['failure']['kind'], 'unverified_data')
            self.assertEqual(result['failure']['reason'], 'reference outside section')

    def test_decoder_count_and_entry_limits_typed(self):
        self.root.context_cache = {i: (SIMPLE, []) for i in range(4096)}
        with self.assertRaisesRegex(graph.reader.DecoderBudgetExceeded, 'context count bound'):
            self.root.context_values(4096)
        self.root.context_cache.clear()
        self.root.contexts = (SIMPLE >> 16, SIMPLE & 0xffff, 0x8000)
        self.root.context_entry_count = 100000
        with self.assertRaisesRegex(graph.reader.DecoderBudgetExceeded, 'total context entry bound'):
            self.root.context_values(0)

    def test_decoder_key_and_depth_limits_typed(self):
        with self.assertRaisesRegex(graph.reader.DecoderBudgetExceeded, 'key bound'):
            graph.reader.ContextTrie([0x30, 97, 0x8000], max_key=0).entries(0)
        with self.assertRaisesRegex(graph.reader.DecoderBudgetExceeded, 'traversal bound'):
            graph.reader.ContextTrie([0x30, 97] * 130 + [0x8000], max_key=256).entries(0)

    def test_edge_budget(self):
        self.root.context_values = lambda _: (SIMPLE, SIMPLE)
        g = graph.StructuralGraph(self.root, max_edges=1)
        with self.assertRaisesRegex(graph.GraphFailure, 'edge bound'):
            g.rank(0xc8, 65)
        self.assertFalse(g.ranks)

    def test_complete_synthetic_graph(self):
        result = graph.inspect(valid_fixture())
        self.assertTrue(result['allNonNulScalarRootsCompleted'])
        self.assertTrue(result['structuralGraphAcyclic'])
        self.assertEqual(result['rootCountCompleted'], 1112063)
        self.assertEqual(result['maxCompletedRank'], 0)
        self.assertFalse(result['consumerTerminationProven'])

    def test_prefix_keeps_argument(self):
        self.root.context_values = lambda _: (SIMPLE, 0xffffffff)
        self.assertEqual(self.g.rank(0xc8, 65), 1)
        with self.assertRaises(graph.reader.Unverified):
            self.g.rank(0xc8, -1)

    def test_contraction_default_keeps_caller(self):
        self.root.context_values = lambda _: (0xffffffff, SIMPLE)
        self.assertEqual(self.g.rank(0xc9, 65), 1)
        self.assertIn((0xffffffff, 65), self.g.ranks)
        self.assertNotIn((0xffffffff, -1), self.g.ranks)
        self.assertIn((SIMPLE, -1), self.g.ranks)
        self.assertIn((SIMPLE, 65), self.g.ranks)

    def test_contraction_trie_sentinel_checked(self):
        self.root.context_values = lambda _: (SIMPLE, 0xffffffff)
        with self.assertRaises(graph.reader.Unverified):
            self.g.rank(0xc9, 65)
        self.assertNotIn((0xc9, 65), self.g.ranks)

    def test_no_ce_default_and_trie_rejected(self):
        for values in ((1, SIMPLE), (SIMPLE, 1)):
            self.root.context_values = lambda _, values=values: values
            with self.assertRaises(graph.reader.Unverified):
                self.g.rank(0xc9, 65)

    def test_actual_context_decoder(self):
        self.root.contexts = (SIMPLE >> 16, SIMPLE & 0xffff, 0x30, 97,
                              0xffff, SIMPLE >> 16, SIMPLE & 0xffff)
        self.assertEqual(self.g.rank(0xc9, 65), 1)
        self.root.contexts = ()
        self.root.context_cache.clear()
        with self.assertRaises(graph.reader.Unverified):
            self.g.rank(0xc9, 66)

    def test_jamo_all_children_and_exact_scalar_key(self):
        self.assertEqual(self.g.rank(0xcc, 0xac00), 1)
        jamo = [SIMPLE] * 67
        jamo[40] = 0xffffffff  # T child only exists in the next syllable.
        self.root.jamo = jamo
        with self.assertRaises(graph.reader.Unverified):
            self.g.rank(0xcc, 0xac01)

    def test_fast_jamo_not_recursive(self):
        self.assertEqual(self.g.rank(0x1cc, 0xac00), 0)
        self.root.jamo = [0xca] * 67
        with self.assertRaises(graph.reader.Unverified):
            self.g.rank(0x1cc, 0xac01)

    def test_full_root_universe(self):
        roots = list(graph.scalars())
        self.assertEqual(len(roots), 1112063)
        self.assertEqual((roots[0], roots[-1]), (1, 0x10ffff))
        self.assertNotIn(0xd800, roots)

    def test_partial_universe_cannot_claim_complete(self):
        with patch.object(graph, 'scalars', return_value=iter((65,))):
            result = graph.inspect(fixture())
        self.assertFalse(result['allNonNulScalarRootsCompleted'])
        self.assertIsNone(result['structuralGraphAcyclic'])
        self.assertFalse(result['offsetsProven'])
        self.assertIsNone(result['delimiterMappingEvidence'])

    def test_failed_initial_mapping_report(self):
        result = graph.inspect(fixture(td=[0xca] * 192))
        # Fixture digits resolve to direct mappings, but lead-unit entries do not
        # carry a lead tag; it must stop at supplementary input without success.
        self.assertFalse(result['allNonNulScalarRootsCompleted'])
        self.assertEqual(result['failure']['rootScalar'], 0x10000)
        self.assertEqual(result['failure']['kind'], 'unverified_data')
        self.assertEqual(result['failure']['reason'], 'lead-unit tag')
        self.assertIsNone(result['delimiterMappingEvidence'])

    def test_initial_summary_rejections_reported(self):
        for lead, reason in ((0x1cd, 'root lead summary requires missing base'),
                             (0xcd, 'implicit lead summary mismatch')):
            with self.subTest(lead=lead):
                result = graph.inspect(valid_fixture(lead))
                self.assertEqual(result['failure'], {
                    'kind': 'unverified_data', 'reason': reason, 'rootScalar': 0x10000})
                self.assertEqual(result['rootCountCompleted'], 0x10000 - 0x800 - 1)
                self.assertIsNone(result['structuralGraphAcyclic'])

    def test_cli_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'root.bin'
            raw = valid_fixture()
            path.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            done = subprocess.run([sys.executable, '-B', str(SCRIPT), '--root-data',
                                   str(path), '--sha256', digest], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stderr, '')
        result = json.loads(done.stdout)
        self.assertEqual(result['rootSha256'], digest)
        self.assertEqual(result['rootCountCompleted'], 1112063)
        self.assertTrue(result['structuralGraphAcyclic'])
        evidence = result['delimiterMappingEvidence']
        self.assertTrue(evidence['colonSingleNonzeroRawHalf'])
        self.assertTrue(evidence['colonAbsentFromContextKeys'])
        self.assertFalse(evidence['delimiterEntryStateProven'])
        for key in ('acceptanceTable', 'offsetsProven', 'consumerIdentityProven',
                    'consumerTerminationProven', 'inputProfileVerified'):
            self.assertFalse(result[key])

    def test_cli_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'root.bin'
            raw = fixture(td=[0xc0] * 192)
            path.write_bytes(raw)
            base = [sys.executable, '-B', str(SCRIPT), '--root-data', str(path), '--sha256']
            bad = subprocess.run(base + ['wrong'], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)
            self.assertEqual(bad.stdout, '')
            unresolved = subprocess.run(base + [hashlib.sha256(raw).hexdigest()],
                                        capture_output=True, text=True)
            self.assertEqual(unresolved.returncode, 2)
            result = json.loads(unresolved.stdout)
            self.assertIsNone(result['structuralGraphAcyclic'])
            self.assertIsNone(result['delimiterMappingEvidence'])
            self.assertEqual(result['failure']['kind'], 'unsupported_dispatch')
        usage = subprocess.run([sys.executable, '-B', str(SCRIPT)], capture_output=True)
        self.assertEqual(usage.returncode, 1)
        self.assertEqual(usage.stdout, b'')

    def test_cli_populated_context_observations(self):
        for key, colon in ((58, SIMPLE), (97, SIMPLE), (97, 0)):
            with self.subTest(key=key, colon=colon), tempfile.TemporaryDirectory() as directory:
                raw = valid_fixture(colon=colon, context_key=key)
                path = Path(directory) / 'root.bin'
                path.write_bytes(raw)
                digest = hashlib.sha256(raw).hexdigest()
                done = subprocess.run(
                    [sys.executable, '-B', str(SCRIPT), '--root-data', str(path),
                     '--sha256', digest], capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(done.stderr, '')
                result = json.loads(done.stdout)
                self.assertEqual(result['rootSha256'], digest)
                self.assertTrue(result['allNonNulScalarRootsCompleted'])
                self.assertEqual(result['rootCountCompleted'], 1112063)
                self.assertTrue(result['structuralGraphAcyclic'])
                self.assertEqual(result['contextTries'], 1)
                evidence = result['delimiterMappingEvidence']
                self.assertEqual(evidence['contextEntriesExamined'], 1)
                self.assertEqual(evidence['contextKeysContainingColon'], int(key == 58))
                self.assertEqual(evidence['colonAbsentFromContextKeys'], key != 58)
                self.assertEqual(evidence['colonCE32'], f'{colon:08x}')
                self.assertEqual(evidence['colonFirstRawHalf'], colon)
                self.assertEqual(evidence['colonSecondRawHalf'], 0)
                self.assertEqual(evidence['colonSingleNonzeroRawHalf'], colon != 0)
                self.assertFalse(evidence['delimiterEntryStateProven'])
                for flag in ('acceptanceTable', 'inputProfileVerified', 'offsetsProven',
                             'consumerIdentityProven', 'consumerTerminationProven'):
                    self.assertFalse(result[flag])


if __name__ == '__main__':
    unittest.main()
